"""
AutoSchedule — Scheduling Engine (v3)
======================================

PRIMARY  : Google OR-Tools CP-SAT  (ILP solver)
FALLBACK : Preference-aware greedy (used if CP-SAT times out or fails)

Session types handled
──────────────────────
  theory    → all hours in a lecture hall
  practical → all hours in a lab (type determined by unit + programme domain)
  hybrid    → split: theory_hours in lecture hall + lab_hours in a lab,
              scheduled on DIFFERENT days whenever possible

Lab room assignment
────────────────────
  1. preferred_lab_type on the Unit (explicit override)
  2. domain_category on the Programme (e.g. ict → computer+physics lab)
  3. All lab types (absolute fallback)

  Even distribution: rooms of the same type are sorted by current usage
  count so the engine prefers the least-loaded lab.

CP-SAT model (per programme / year-group)
──────────────────────────────────────────
  Hybrid units are split into two "schedule parts":
      - theory part  (required_hours = unit.theory_hours, rooms = lecture halls)
      - lab    part  (required_hours = unit.lab_hours,    rooms = labs)

  Decision variable: x[part_idx, block_idx, room_idx] ∈ {0,1}
  where block_idx encodes a consecutive run of required_hours slots on one day.

  Hard constraints
    1. Coverage:            Σ_{b,r} x[p,b,r] = 1        for each part p
    2. Room non-overlap:    Σ_{p,b: t∈b} x[p,b,r] ≤ 1  for each (room, slot)
    3. Lecturer uniqueness: Σ_{p,b: t∈b} x[p,b,r] ≤ 1  for each (lecturer, slot)
    4. Programme uniqueness:Σ_{p,b: t∈b} x[p,b,r] ≤ 1  for each (prog, slot)

  Soft objective: minimise Σ_{p,b,r} x[p,b,r] × (5 − pref_score(lecturer, b))

Global cross-programme state (shared between all programme solves):
    global_room_slots      : {(room_id, slot_id): True}
    global_lecturer_slots  : {(lecturer_id, slot_id): True}
    global_programme_slots : {(prog_key, slot_id): True}
    break_slots_lecturer   : {(lecturer_id, slot_id): True}   [1-slot gap]
    break_slots_programme  : {(prog_key, slot_id): True}
"""

import re
import uuid
import time
from collections import defaultdict
from dataclasses import dataclass, field
from django.db import transaction
from .models import Unit, Room, TimeSlot, TimetableEntry, Programme, Lecturer, LecturerPreference

# ── Constants ─────────────────────────────────────────────────────────────────
NEUTRAL_PREFERENCE = 3      # score used when no preference is recorded (1-5)
MAX_SOLVE_SECONDS  = 45     # CP-SAT wall-clock time limit per group


# ─────────────────────────────────────────────────────────────────────────────
# SchedulePart — flattened view of one unit's theory or lab portion
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SchedulePart:
    """
    Represents one scheduling task derived from a Unit.
    A theory Unit yields one SchedulePart; a practical Unit yields one;
    a hybrid Unit yields TWO (one theory + one lab).
    """
    unit:           object          # reference to the actual Unit ORM object
    unit_id:        int
    lecturer_id:    int | None
    programme_id:   int | None
    prog_key:       object          # (prog.id, year) or prog.id
    required_hours: int             # hours this part must be scheduled
    room_types:     list            # valid room_type values for this part
    part_label:     str             # 'theory', 'lab', or 'main'


def expand_unit(unit, prog_key):
    """
    Convert a Unit into one or two SchedulePart objects.
    Hybrid → [theory_part, lab_part]
    Theory / Practical → [main_part]
    """
    base = dict(
        unit=unit,
        unit_id=unit.id,
        lecturer_id=unit.lecturer_id,
        programme_id=unit.programme_id,
        prog_key=prog_key,
    )
    stype = unit.session_type or 'theory'

    if stype == 'theory':
        return [SchedulePart(**base, required_hours=unit.required_hours,
                             room_types=['lecture_hall'],
                             part_label='main')]

    if stype == 'practical':
        return [SchedulePart(**base, required_hours=unit.required_hours,
                             room_types=unit.lab_room_types or ['computer_lab'],
                             part_label='main')]

    # hybrid
    th = unit.theory_hours
    lh = unit.lab_hours
    parts = []
    if th > 0:
        parts.append(SchedulePart(**base, required_hours=th,
                                  room_types=['lecture_hall'],
                                  part_label='theory'))
    if lh > 0:
        parts.append(SchedulePart(**base, required_hours=lh,
                                  room_types=unit.lab_room_types or ['computer_lab'],
                                  part_label='lab'))
    return parts or [SchedulePart(**base, required_hours=unit.required_hours,
                                  room_types=['lecture_hall'], part_label='main')]


# ─────────────────────────────────────────────────────────────────────────────
# Utility helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_year_group(unit_code):
    numbers = re.findall(r'\d+', unit_code)
    if numbers:
        n = int(numbers[0])
        if 100 <= n <= 199: return 1
        if 200 <= n <= 299: return 2
        if 300 <= n <= 399: return 3
        if 400 <= n <= 499: return 4
    return 1


def _slot_available(slot_id, room_id, lecturer_id, prog_key,
                    global_room_slots, global_lecturer_slots,
                    global_programme_slots,
                    break_slots_lecturer, break_slots_programme):
    if global_room_slots.get((room_id, slot_id)):
        return False
    if lecturer_id and global_lecturer_slots.get((lecturer_id, slot_id)):
        return False
    if global_programme_slots.get((prog_key, slot_id)):
        return False
    if lecturer_id and break_slots_lecturer.get((lecturer_id, slot_id)):
        return False
    if break_slots_programme.get((prog_key, slot_id)):
        return False
    return True


def _mark_slots(slot_ids, room_id, lecturer_id, prog_key,
                global_room_slots, global_lecturer_slots, global_programme_slots,
                room_usage):
    for sid in slot_ids:
        global_room_slots[(room_id, sid)] = True
        if lecturer_id:
            global_lecturer_slots[(lecturer_id, sid)] = True
        global_programme_slots[(prog_key, sid)] = True
    room_usage[room_id] = room_usage.get(room_id, 0) + len(slot_ids)


def _mark_break(break_slot_id, lecturer_id, prog_key,
                break_slots_lecturer, break_slots_programme):
    if break_slot_id is None:
        return
    if lecturer_id:
        break_slots_lecturer[(lecturer_id, break_slot_id)] = True
    break_slots_programme[(prog_key, break_slot_id)] = True


# ─────────────────────────────────────────────────────────────────────────────
# Preference scoring
# ─────────────────────────────────────────────────────────────────────────────

def _score_block(block, lecturer_id, pref_lookup):
    if not lecturer_id:
        return NEUTRAL_PREFERENCE * len(block)
    return sum(
        pref_lookup.get((lecturer_id, s.id), NEUTRAL_PREFERENCE)
        for s in block
    )


def _compute_psr(results_list):
    if not results_list:
        return 'N/A'
    total_score = sum(r[1] for r in results_list)
    total_max   = sum(r[2] for r in results_list)
    if total_max == 0:
        return 'N/A'
    if total_score == NEUTRAL_PREFERENCE * len(results_list):
        return 'N/A (no preferences set)'
    return f"{round((total_score / total_max) * 100)}%"


# ─────────────────────────────────────────────────────────────────────────────
# Room picker with even load distribution
# ─────────────────────────────────────────────────────────────────────────────

def _pick_rooms(room_types, all_rooms, room_usage):
    """
    Return candidate rooms matching room_types, sorted by usage (least-used first).
    This ensures even distribution across labs of the same type.
    """
    candidates = [r for r in all_rooms
                  if r.room_type in room_types and r.capacity > 0]
    # Sort by sessions already assigned (ascending), then by id for determinism
    candidates.sort(key=lambda r: (room_usage.get(r.id, 0), r.id))
    return candidates


# ─────────────────────────────────────────────────────────────────────────────
# Greedy block finder
# ─────────────────────────────────────────────────────────────────────────────

def _find_best_block(size, day_slots, room, lecturer_id, prog_key,
                     global_room_slots, global_lecturer_slots,
                     global_programme_slots,
                     break_slots_lecturer, break_slots_programme,
                     pref_lookup):
    n = len(day_slots)
    valid_blocks = []
    for i in range(n - size + 1):
        block = day_slots[i:i + size]
        if all(
            _slot_available(
                s.id, room.id, lecturer_id, prog_key,
                global_room_slots, global_lecturer_slots, global_programme_slots,
                break_slots_lecturer, break_slots_programme
            )
            for s in block
        ):
            score = _score_block(block, lecturer_id, pref_lookup)
            valid_blocks.append((score, i, block))
    if not valid_blocks:
        return None
    valid_blocks.sort(key=lambda x: (-x[0], x[1]))
    return valid_blocks[0][2]


# ─────────────────────────────────────────────────────────────────────────────
# Greedy scheduler for a single SchedulePart
# ─────────────────────────────────────────────────────────────────────────────

def _assign_part_greedy(part, all_rooms, slots_by_day,
                        global_room_slots, global_lecturer_slots,
                        global_programme_slots,
                        break_slots_lecturer, break_slots_programme,
                        pref_lookup, room_usage,
                        exclude_days=None):
    """
    Preference-aware greedy assignment of one SchedulePart.
    exclude_days: set of day strings already used by the sibling part (hybrid).
    Returns list of (TimetableEntry, block_score, max_possible_score).
    """
    exclude_days = exclude_days or set()
    needed      = part.required_hours
    lect_id     = part.lecturer_id
    lect_obj    = part.unit.lecturer
    prog_key    = part.prog_key
    results     = []
    remaining   = needed

    # Order days: prefer days NOT used by sibling (hybrid even spread)
    days = sorted(slots_by_day.keys(),
                  key=lambda d: (d in exclude_days, d))
    rooms = _pick_rooms(part.room_types, all_rooms, room_usage)

    for block_size in [3, 2, 1]:
        if remaining <= 0:
            break
        if block_size > remaining:
            continue
        for room in rooms:
            if remaining <= 0:
                break
            for day in days:
                if remaining <= 0 or block_size > remaining:
                    break
                block = _find_best_block(
                    block_size, slots_by_day[day], room,
                    lect_id, prog_key,
                    global_room_slots, global_lecturer_slots,
                    global_programme_slots,
                    break_slots_lecturer, break_slots_programme,
                    pref_lookup
                )
                if block is None:
                    continue

                b_score  = _score_block(block,  lect_id, pref_lookup)
                max_p    = 5 * len(block)
                group_id = uuid.uuid4()
                slot_ids = [s.id for s in block]
                _mark_slots(slot_ids, room.id, lect_id, prog_key,
                            global_room_slots, global_lecturer_slots,
                            global_programme_slots, room_usage)

                for s in block:
                    results.append((
                        TimetableEntry(
                            unit=part.unit, room=room, timeslot=s,
                            lecturer=lect_obj, session_group_id=group_id
                        ),
                        b_score, max_p
                    ))

                last_idx = slots_by_day[day].index(block[-1])
                break_slot = (
                    slots_by_day[day][last_idx + 1]
                    if last_idx + 1 < len(slots_by_day[day]) else None
                )
                _mark_break(
                    break_slot.id if break_slot else None,
                    lect_id, prog_key,
                    break_slots_lecturer, break_slots_programme
                )
                remaining -= block_size
                break

    return results


# ─────────────────────────────────────────────────────────────────────────────
# CP-SAT solver
# ─────────────────────────────────────────────────────────────────────────────

def _solve_cpsat(parts, all_rooms, slots_by_day, prog_key,
                 global_room_slots, global_lecturer_slots,
                 global_programme_slots,
                 break_slots_lecturer, break_slots_programme,
                 pref_lookup, room_usage, label=''):
    """
    Solve a list of SchedulePart objects using OR-Tools CP-SAT.
    Returns ('CP-SAT', results_list) or (status_name, []) on failure.
    """
    try:
        from ortools.sat.python import cp_model
    except (ImportError, Exception) as e:
        print(f"[CP-SAT] {label}OR-Tools unavailable: {e}")
        return 'IMPORT_ERROR', []

    model = cp_model.CpModel()

    # ── Enumerate feasible (block, room) candidates per part ──────────────
    x_vars         = []   # x_vars[p_idx] = {b_idx: BoolVar}
    candidate_data = []   # candidate_data[p_idx] = [(block_slots, room, score, max_score)]

    for p_idx, part in enumerate(parts):
        rooms_for_part  = _pick_rooms(part.room_types, all_rooms, room_usage)
        required_hours  = part.required_hours
        lect_id         = part.lecturer_id
        part_cands      = []

        for day, day_slots in slots_by_day.items():
            n = len(day_slots)
            for start_i in range(n - required_hours + 1):
                block = day_slots[start_i:start_i + required_hours]

                # Check global lecturer / prog availability (non-room)
                if lect_id and any(
                    global_lecturer_slots.get((lect_id, s.id)) or
                    break_slots_lecturer.get((lect_id, s.id))
                    for s in block
                ):
                    continue

                if any(break_slots_programme.get((prog_key, s.id)) for s in block):
                    continue

                for room in rooms_for_part:
                    # Check global room occupancy
                    if any(global_room_slots.get((room.id, s.id)) for s in block):
                        continue

                    score  = _score_block(block, lect_id, pref_lookup)
                    max_sc = 5 * len(block)
                    part_cands.append((block, room, score, max_sc))

        x_vars.append({})
        candidate_data.append(part_cands)
        for b_idx in range(len(part_cands)):
            var = model.NewBoolVar(f"x_p{p_idx}_b{b_idx}")
            x_vars[p_idx][b_idx] = var

    # ── Hard Constraint 1: Each part scheduled exactly once ───────────────
    for p_idx, part in enumerate(parts):
        all_vars = list(x_vars[p_idx].values())
        if not all_vars:
            print(f"[CP-SAT] {label}{part.unit.code}({part.part_label}): no feasible slot.")
            model.Add(cp_model.LinearExpr.Sum([]) == 1)  # force INFEASIBLE
        else:
            model.AddExactlyOne(all_vars)

    # ── Build slot-level index maps ────────────────────────────────────────
    room_slot_vars = defaultdict(list)
    lect_slot_vars = defaultdict(list)
    prog_slot_vars = defaultdict(list)

    for p_idx, part in enumerate(parts):
        lect_id = part.lecturer_id
        for b_idx, (block, room, _, __) in enumerate(candidate_data[p_idx]):
            var = x_vars[p_idx][b_idx]
            for s in block:
                room_slot_vars[(room.id, s.id)].append(var)
                if lect_id:
                    lect_slot_vars[(lect_id, s.id)].append(var)
                prog_slot_vars[(prog_key, s.id)].append(var)

    # ── Hard Constraint 2: Room non-overlap ───────────────────────────────
    for var_list in room_slot_vars.values():
        if len(var_list) > 1:
            model.AddAtMostOne(var_list)

    # ── Hard Constraint 3: Lecturer non-overlap ───────────────────────────
    for var_list in lect_slot_vars.values():
        if len(var_list) > 1:
            model.AddAtMostOne(var_list)

    # ── Hard Constraint 4: Programme non-overlap ──────────────────────────
    for var_list in prog_slot_vars.values():
        if len(var_list) > 1:
            model.AddAtMostOne(var_list)

    # ── Hard Constraint 5: Student Break Enforcement (no back-to-back) ───
    # For each programme, for any two DIFFERENT session parts, force at least 
    # one slot gap if they are on the same day.
    # Optimized: If a session ends at slot i, no other session start at i+1.
    ends_at   = defaultdict(list) # ends_at[(day, i)] = [vars]
    starts_at = defaultdict(list) # starts_at[(day, i)] = [vars]

    # Pre-map slot IDs to indices for fast lookup
    slot_id_to_idx = {}
    for day, day_slots in slots_by_day.items():
        for i, s in enumerate(day_slots):
            slot_id_to_idx[s.id] = i

    for p_idx, part in enumerate(parts):
        for b_idx, (block, room, _, __) in enumerate(candidate_data[p_idx]):
            var = x_vars[p_idx][b_idx]
            day      = block[0].day
            start_idx = slot_id_to_idx[block[0].id]
            end_idx   = slot_id_to_idx[block[-1].id]
            
            starts_at[(day, start_idx)].append(var)
            ends_at[(day, end_idx)].append(var)

    for day, day_slots in slots_by_day.items():
        for i in range(len(day_slots) - 1):
            # If any session ends at i, nothing can start at i+1. 
            # (Note: same session extending across i and i+1 is allowed because 
            # its 'start' is at some j <= i and its 'end' is at some k >= i+1).
            
            e_vars = ends_at[(day, i)]
            s_vars = starts_at[(day, i+1)]
            
            if e_vars and s_vars:
                # model.Add(Sum(e_vars) + Sum(s_vars) <= 1)
                model.AddAtMostOne(e_vars + s_vars)




    # ── Soft objective: minimise preference penalty ────────────────────────
    penalty_terms = []
    for p_idx in range(len(parts)):
        for b_idx, (block, room, pref_score, max_score) in enumerate(
                candidate_data[p_idx]):
            penalty = max_score - pref_score
            if penalty > 0:
                penalty_terms.append(x_vars[p_idx][b_idx] * penalty)
    if penalty_terms:
        model.Minimize(cp_model.LinearExpr.Sum(penalty_terms))

    # ── Solve ──────────────────────────────────────────────────────────────
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = MAX_SOLVE_SECONDS
    solver.parameters.log_search_progress = False
    solver.parameters.num_search_workers  = 4

    status = solver.Solve(model)
    status_name = solver.StatusName(status)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print(f"[CP-SAT] {label}Status: {status_name} — falling back to greedy.")
        return status_name, []

    # ── Extract solution ───────────────────────────────────────────────────
    results = []
    for p_idx, part in enumerate(parts):
        lect_id  = part.lecturer_id
        lect_obj = part.unit.lecturer
        for b_idx, (block, room, pref_score, max_score) in enumerate(
                candidate_data[p_idx]):
            if solver.Value(x_vars[p_idx][b_idx]):
                group_id = uuid.uuid4()
                slot_ids = [s.id for s in block]
                _mark_slots(slot_ids, room.id, lect_id, prog_key,
                            global_room_slots, global_lecturer_slots,
                            global_programme_slots, room_usage)
                for s in block:
                    results.append((
                        TimetableEntry(
                            unit=part.unit, room=room, timeslot=s,
                            lecturer=lect_obj, session_group_id=group_id
                        ),
                        pref_score, max_score
                    ))
                day_slots = slots_by_day[block[0].day]
                last_idx  = day_slots.index(block[-1])
                break_slot = (
                    day_slots[last_idx + 1]
                    if last_idx + 1 < len(day_slots) else None
                )
                _mark_break(
                    break_slot.id if break_slot else None,
                    lect_id, prog_key,
                    break_slots_lecturer, break_slots_programme
                )
                break  # each part has exactly one assigned block

    print(f"[CP-SAT] {label}Status: {status_name} | "
          f"{len(results)}/{sum(p.required_hours for p in parts)} slots "
          f"| {solver.WallTime():.1f}s")
    return 'CP-SAT', results


# ─────────────────────────────────────────────────────────────────────────────
# Programme-level orchestrator
# ─────────────────────────────────────────────────────────────────────────────

def _solve_programme(units, all_rooms, slots_by_day, prog_key,
                     global_room_slots, global_lecturer_slots,
                     global_programme_slots,
                     break_slots_lecturer, break_slots_programme,
                     pref_lookup, room_usage, label=''):
    """
    Schedule all units for one programme / year-group.
    Hybrid units are expanded into theory + lab parts.
    Tries CP-SAT first, falls back to greedy per-part.
    """
    # Expand units into scheduling parts
    parts = []
    for unit in units:
        parts.extend(expand_unit(unit, prog_key))

    status, cp_results = _solve_cpsat(
        parts, all_rooms, slots_by_day, prog_key,
        global_room_slots, global_lecturer_slots, global_programme_slots,
        break_slots_lecturer, break_slots_programme,
        pref_lookup, room_usage, label=label
    )

    if status == 'CP-SAT':
        for unit in units:
            n   = sum(1 for r in cp_results if r[0].unit_id == unit.id)
            psr = _compute_psr([r for r in cp_results if r[0].unit_id == unit.id])
            print(f"[OK  ] {label}{unit.code}: {n}/{unit.required_hours} | {psr}")
        return 'CP-SAT', cp_results

    # ── Greedy fallback ────────────────────────────────────────────────────
    print(f"[FALL] {label}Greedy fallback for {len(parts)} parts.")
    greedy_results = []

    # For hybrid units, track which days were used by the theory part
    # so the lab part can be placed on a different day.
    used_days_by_unit = defaultdict(set)

    for part in parts:
        exclude = used_days_by_unit.get(part.unit_id, set()) \
                  if part.part_label == 'lab' else set()
        res = _assign_part_greedy(
            part, all_rooms, slots_by_day,
            global_room_slots, global_lecturer_slots, global_programme_slots,
            break_slots_lecturer, break_slots_programme,
            pref_lookup, room_usage,
            exclude_days=exclude
        )
        greedy_results.extend(res)

        # Record days used so the sibling lab part prefers other days
        for entry, _, __ in res:
            used_days_by_unit[part.unit_id].add(entry.timeslot.day)

        n = len(res)
        print(
            f"[{'OK  ' if n >= part.required_hours else 'FAIL'}] "
            f"{label}{part.unit.code}({part.part_label}): "
            f"{n}/{part.required_hours} | "
            f"{_compute_psr(res)}"
        )

    return 'Greedy (fallback)', greedy_results


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def generate_timetable():
    """
    Main scheduling entry point called by views.py.

    Workflow:
      1. Load programmes, units, rooms, timeslots, preferences.
      2. Split large programmes into year-groups (>15 units).
      3. For each group: expand hybrid units → try CP-SAT → greedy fallback.
      4. Persist TimetableEntry rows atomically.
      5. Return results dict including PSR and engine used.
    """
    results = {
        'status':                    'failed',
        'entries_created':           0,
        'solve_time':                0,
        'solver_status':             'N/A',
        'programme_results':         [],
        'conflicts':                 [],
        'message':                   '',
        'preference_satisfaction_rate': None,
        'preference_stats':          {},
    }

    start = time.perf_counter()

    try:
        # ── 1. Load data ──────────────────────────────────────────────────
        programmes = list(Programme.objects.all())
        units      = list(Unit.objects.select_related(
            'lecturer', 'programme'
        ).all())
        all_rooms  = list(Room.objects.filter(is_available=True))
        timeslots  = list(TimeSlot.objects.order_by('day', 'start_time'))

        if not programmes or not units or not all_rooms or not timeslots:
            results['message'] = (
                'Critical data missing (Programmes, Units, Rooms, or Slots).'
            )
            return results

        # ── 2. Preference lookup ──────────────────────────────────────────
        pref_lookup = {
            (p.lecturer_id, p.timeslot_id): p.preference_score
            for p in LecturerPreference.objects.select_related(
                'lecturer', 'timeslot'
            ).all()
        }
        print(f"[AI]  Loaded {len(pref_lookup)} preference records.")

        # ── 3. Slot index ─────────────────────────────────────────────────
        slots_by_day = {}
        for ts in timeslots:
            slots_by_day.setdefault(ts.day, []).append(ts)

        # ── 4. Global constraint trackers ─────────────────────────────────
        global_room_slots      = {}
        global_lecturer_slots  = {}
        global_programme_slots = {}
        break_slots_lecturer   = {}
        break_slots_programme  = {}
        room_usage             = {}   # {room_id: session_count}

        # ── 5. Schedule each programme ────────────────────────────────────
        all_results  = []
        any_success  = False
        engines_used = set()

        for prog in programmes:
            prog_units = [u for u in units if u.programme_id == prog.id]
            if not prog_units:
                continue

            if len(prog_units) > 15:
                year_groups = {}
                for u in prog_units:
                    yr = get_year_group(u.code)
                    year_groups.setdefault(yr, []).append(u)

                print(f"[SPLT] {prog.name}: split into "
                      f"{len(year_groups)} year-group(s).")

                for yr in sorted(year_groups.keys()):
                    yr_units = year_groups[yr]
                    pg_key   = (prog.id, yr)
                    lbl      = f"{prog.name} Y{yr} | "

                    method, pg_res = _solve_programme(
                        yr_units, all_rooms, slots_by_day, pg_key,
                        global_room_slots, global_lecturer_slots,
                        global_programme_slots,
                        break_slots_lecturer, break_slots_programme,
                        pref_lookup, room_usage, label=lbl
                    )
                    engines_used.add(method)
                    total_needed = sum(u.required_hours for u in yr_units)
                    scheduled    = len(pg_res)
                    status_s     = 'success' if scheduled >= total_needed else 'partial'
                    psr          = _compute_psr(pg_res)

                    results['programme_results'].append({
                        'programme':              f"{prog.name} - Year {yr}",
                        'status':                 status_s,
                        'entries':                scheduled,
                        'method':                 method,
                        'solver_status':          status_s.upper(),
                        'preference_satisfaction': psr,
                    })
                    if pg_res:
                        all_results.extend(pg_res)
                        any_success = True
                    else:
                        results['conflicts'].append(f"Failed: {prog.name} Y{yr}")

            else:
                pg_key = prog.id
                lbl    = f"{prog.name} | "

                method, pg_res = _solve_programme(
                    prog_units, all_rooms, slots_by_day, pg_key,
                    global_room_slots, global_lecturer_slots,
                    global_programme_slots,
                    break_slots_lecturer, break_slots_programme,
                    pref_lookup, room_usage, label=lbl
                )
                engines_used.add(method)
                total_needed = sum(u.required_hours for u in prog_units)
                scheduled    = len(pg_res)
                status_s     = 'success' if scheduled >= total_needed else 'partial'
                psr          = _compute_psr(pg_res)

                results['programme_results'].append({
                    'programme':              prog.name,
                    'status':                 status_s,
                    'entries':                scheduled,
                    'method':                 method,
                    'solver_status':          status_s.upper(),
                    'preference_satisfaction': psr,
                })
                if pg_res:
                    all_results.extend(pg_res)
                    any_success = True
                else:
                    results['conflicts'].append(f"Failed: {prog.name}")

        # ── 6. Extract entries ─────────────────────────────────────────────
        all_new_entries = [r[0] for r in all_results]

        # ── 7. Missed session diagnostic ───────────────────────────────────
        assigned_count = {}
        for e in all_new_entries:
            assigned_count[e.unit_id] = assigned_count.get(e.unit_id, 0) + 1

        missed = []
        for u in units:
            got = assigned_count.get(u.id, 0)
            if got < u.required_hours:
                prog_name = u.programme.name if u.programme else '?'
                missed.append((u.code, prog_name, u.required_hours, got))

        if missed:
            print(f"[MISS] {len(missed)} unit(s) under-scheduled:")
            for code, pname, needed, got in missed:
                print(f"  {code} ({pname}): need {needed}, got {got}")
            results['conflicts'].extend(
                [f"{c} ({p}): need {n}, got {g}" for c, p, n, g in missed]
            )
        else:
            print("[OK  ] All units fully scheduled!")

        # ── 8. Print lab distribution summary ─────────────────────────────
        if room_usage:
            print("[LAB ] Room usage distribution:")
            for rm in sorted(all_rooms, key=lambda r: r.room_type):
                cnt = room_usage.get(rm.id, 0)
                if cnt:
                    print(f"        {rm.name} ({rm.room_type}): {cnt} session-hours")

        # ── 9. PSR ────────────────────────────────────────────────────────
        global_psr = _compute_psr(all_results)
        results['preference_satisfaction_rate'] = global_psr
        results['preference_stats'] = {
            'preferences_loaded':  len(pref_lookup),
            'sessions_scheduled':  len(all_new_entries),
            'psr':                 global_psr,
        }
        engine_summary = ' + '.join(sorted(engines_used)) or 'None'
        results['solver_status'] = engine_summary
        print(f"[AI]  Global PSR: {global_psr}")

        # ── 10. Persist ────────────────────────────────────────────────────
        if any_success:
            with transaction.atomic():
                TimetableEntry.objects.all().delete()
                TimetableEntry.objects.bulk_create(all_new_entries)

            results['entries_created'] = len(all_new_entries)
            results['status']  = 'success' if not missed else 'partial'
            results['message'] = (
                f"Scheduling complete. {len(all_new_entries)} sessions assigned "
                f"using [{engine_summary}] with preference optimisation "
                f"(PSR: {global_psr})."
            )
        else:
            results['message'] = "Scheduler failed — no units could be scheduled."

    except Exception as e:
        import traceback
        results['status']  = 'failed'
        results['message'] = f"System Error: {str(e)}"
        results['conflicts'].append(str(e))
        print(traceback.format_exc())

    results['solve_time'] = round(time.perf_counter() - start, 2)
    return results
