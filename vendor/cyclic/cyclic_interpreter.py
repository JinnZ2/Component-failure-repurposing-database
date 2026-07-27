#!/usr/bin/env python3
"""
Cyclical Programming Language Interpreter
Proof of Concept - Field Operations with Energy Conservation
"""

import re
import math
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass
from enum import Enum

class FieldOperator(Enum):
    GRADIENT = "∇"
    LAPLACIAN = "∇²"
    BIDIRECTIONAL = "⇄"
    UNIDIRECTIONAL = "→"
    CYCLE = "∮"
    PARTIAL_DERIVATIVE = "∂"

@dataclass
class EnergyState:
    """Tracks energy for conservation checking"""
    total_energy: float = 0.0
    kinetic: float = 0.0
    potential: float = 0.0
    entropy: float = 0.0  # Track entropy (S)
    quantum_coherence: float = 0.0  # Quantum superposition measure
    phase_angle: float = 0.0  # Phase in radians

    def __add__(self, other):
        return EnergyState(
            self.total_energy + other.total_energy,
            self.kinetic + other.kinetic,
            self.potential + other.potential,
            self.entropy + other.entropy,
            (self.quantum_coherence + other.quantum_coherence) / 2,
            (self.phase_angle + other.phase_angle) % (2 * math.pi)
        )

    def conserved_with(self, other, tolerance=1e-10):
        return abs(self.total_energy - other.total_energy) < tolerance

    def entropy_increased(self, other):
        """Check 2nd law: entropy must increase or stay same"""
        return other.entropy >= self.entropy - 1e-10

    def in_phase_with(self, other, tolerance=0.1):
        """Check if two states are in phase (resonance)"""
        phase_diff = abs(self.phase_angle - other.phase_angle)
        return phase_diff < tolerance or abs(phase_diff - 2*math.pi) < tolerance

@dataclass
class FieldState:
    """Represents a field with energy and spatial properties"""
    name: str
    energy: EnergyState
    position: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    gradient: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    capacity: float = 1.0  # Regenerative capacity (grows over time)
    age: int = 0  # Cycles since creation
    phase_state: str = "normal"  # normal, liquid, gas, plasma, crystalline
    frequency: float = 1.0  # Oscillation frequency for resonance
    fractal_depth: int = 0  # Recursive generation level
    entangled_with: Optional[str] = None  # Quantum entanglement partner

    def interact_with(self, other_field):
        """Create bidirectional field interaction"""
        # Simple energy exchange model
        energy_exchange = 0.1 * (self.energy.total_energy - other_field.energy.total_energy)
    
        # Entropy increases with interaction
        entropy_increase = abs(energy_exchange) * 0.01
    
        # Phase synchronization tendency
        phase_coupling = 0.1 * (other_field.energy.phase_angle - self.energy.phase_angle)
    
        new_self_energy = EnergyState(
            total_energy=self.energy.total_energy - energy_exchange,
            kinetic=self.energy.kinetic - energy_exchange * 0.6,
            potential=self.energy.potential - energy_exchange * 0.4,
            entropy=self.energy.entropy + entropy_increase,
            quantum_coherence=self.energy.quantum_coherence * 0.99,
            phase_angle=(self.energy.phase_angle + phase_coupling) % (2 * math.pi)
        )
    
        new_other_energy = EnergyState(
            total_energy=other_field.energy.total_energy + energy_exchange,
            kinetic=other_field.energy.kinetic + energy_exchange * 0.6,
            potential=other_field.energy.potential + energy_exchange * 0.4,
            entropy=other_field.energy.entropy + entropy_increase,
            quantum_coherence=other_field.energy.quantum_coherence * 0.99,
            phase_angle=(other_field.energy.phase_angle - phase_coupling) % (2 * math.pi)
        )
    
        return (
            FieldState(self.name, new_self_energy, self.position, self.gradient, 
                      self.capacity, self.age + 1, self.phase_state, self.frequency, 
                      self.fractal_depth, self.entangled_with),
            FieldState(other_field.name, new_other_energy, other_field.position, 
                      other_field.gradient, other_field.capacity, other_field.age + 1,
                      other_field.phase_state, other_field.frequency, other_field.fractal_depth,
                      other_field.entangled_with)
        )

    def quantum_entangle(self, other_field) -> Tuple['FieldState', 'FieldState']:
        """Create quantum entanglement between fields"""
        # Share quantum coherence
        avg_coherence = (self.energy.quantum_coherence + other_field.energy.quantum_coherence) / 2
        boosted = min(avg_coherence + 0.2, 1.0)  # Bounded to [0, 1]

        # Entangled states maintain correlation
        new_self_energy = EnergyState(
            total_energy=self.energy.total_energy,
            kinetic=self.energy.kinetic,
            potential=self.energy.potential,
            entropy=self.energy.entropy,
            quantum_coherence=boosted,
            phase_angle=self.energy.phase_angle
        )

        new_other_energy = EnergyState(
            total_energy=other_field.energy.total_energy,
            kinetic=other_field.energy.kinetic,
            potential=other_field.energy.potential,
            entropy=other_field.energy.entropy,
            quantum_coherence=boosted,
            phase_angle=other_field.energy.phase_angle
        )
    
        return (
            FieldState(self.name, new_self_energy, self.position, self.gradient,
                      self.capacity, self.age, self.phase_state, self.frequency,
                      self.fractal_depth, other_field.name),
            FieldState(other_field.name, new_other_energy, other_field.position,
                      other_field.gradient, other_field.capacity, other_field.age,
                      other_field.phase_state, other_field.frequency, other_field.fractal_depth,
                      self.name)
        )

    def resonate_with(self, other_field) -> Tuple['FieldState', 'FieldState']:
        """Create resonant coupling - amplification when frequencies match"""
        # Calculate frequency match
        freq_diff = abs(self.frequency - other_field.frequency)
        resonance_strength = math.exp(-freq_diff)  # Stronger when frequencies close
    
        # Resonance amplifies both fields
        amplification = 1.0 + 0.2 * resonance_strength
    
        # Phase lock when in resonance
        avg_phase = (self.energy.phase_angle + other_field.energy.phase_angle) / 2
    
        new_self_energy = EnergyState(
            total_energy=self.energy.total_energy * amplification,
            kinetic=self.energy.kinetic * amplification,
            potential=self.energy.potential * amplification,
            entropy=self.energy.entropy,
            quantum_coherence=self.energy.quantum_coherence + 0.1 * resonance_strength,
            phase_angle=avg_phase if resonance_strength > 0.5 else self.energy.phase_angle
        )
    
        new_other_energy = EnergyState(
            total_energy=other_field.energy.total_energy * amplification,
            kinetic=other_field.energy.kinetic * amplification,
            potential=other_field.energy.potential * amplification,
            entropy=other_field.energy.entropy,
            quantum_coherence=other_field.energy.quantum_coherence + 0.1 * resonance_strength,
            phase_angle=avg_phase if resonance_strength > 0.5 else other_field.energy.phase_angle
        )
    
        return (
            FieldState(self.name, new_self_energy, self.position, self.gradient,
                      self.capacity, self.age + 1, self.phase_state, self.frequency,
                      self.fractal_depth, self.entangled_with),
            FieldState(other_field.name, new_other_energy, other_field.position,
                      other_field.gradient, other_field.capacity, other_field.age + 1,
                      other_field.phase_state, other_field.frequency, other_field.fractal_depth,
                      other_field.entangled_with)
        )

    def phase_transition(self, target_phase: str) -> 'FieldState':
        """Undergo phase transition (solid↔liquid↔gas↔plasma)"""
        phase_order = ["crystalline", "normal", "liquid", "gas", "plasma"]
        current_idx = phase_order.index(self.phase_state)
        target_idx = phase_order.index(target_phase)
    
        # Energy required for phase transition
        phase_diff = abs(target_idx - current_idx)
        energy_cost = phase_diff * 10.0
    
        # Check if enough energy available
        if self.energy.total_energy < energy_cost:
            return self  # Not enough energy for transition
    
        # Entropy changes based on phase
        entropy_change = (target_idx - current_idx) * 2.0
    
        new_energy = EnergyState(
            total_energy=self.energy.total_energy - energy_cost,
            kinetic=self.energy.kinetic + energy_cost if target_idx > current_idx else self.energy.kinetic - energy_cost,
            potential=self.energy.potential - energy_cost if target_idx > current_idx else self.energy.potential + energy_cost,
            entropy=self.energy.entropy + abs(entropy_change),
            quantum_coherence=self.energy.quantum_coherence * (0.5 if target_phase == "plasma" else 1.0),
            phase_angle=self.energy.phase_angle
        )
    
        return FieldState(
            self.name, new_energy, self.position, self.gradient,
            self.capacity, self.age + 1, target_phase, self.frequency,
            self.fractal_depth, self.entangled_with
        )

    def fractal_spawn(self, depth: int) -> List['FieldState']:
        """Create fractal copies at smaller scales"""
        spawns = []
        energy_per_spawn = self.energy.total_energy / (2 ** depth)
    
        for i in range(2 ** depth):
            spawn_energy = EnergyState(
                total_energy=energy_per_spawn,
                kinetic=self.energy.kinetic / (2 ** depth),
                potential=self.energy.potential / (2 ** depth),
                entropy=self.energy.entropy / (2 ** depth),
                quantum_coherence=self.energy.quantum_coherence,
                phase_angle=self.energy.phase_angle + i * (2 * math.pi / (2 ** depth))
            )
        
            # Position offset for spatial distribution
            offset = ((i % 2) * 0.1, ((i // 2) % 2) * 0.1, (i // 4) * 0.1)
            new_pos = tuple(p + o for p, o in zip(self.position, offset))
        
            spawn = FieldState(
                f"{self.name}_fractal_{depth}_{i}",
                spawn_energy,
                new_pos,
                self.gradient,
                self.capacity * 0.8,  # Slightly reduced capacity
                0,  # Fresh spawn
                self.phase_state,
                self.frequency * (2 ** depth),  # Higher frequency at smaller scale
                depth,
                None
            )
            spawns.append(spawn)
    
        return spawns

    def spatial_gradient_flow(self, other_field) -> Tuple['FieldState', 'FieldState']:
        """Energy flows based on spatial gradient"""
        # Calculate distance
        dx = other_field.position[0] - self.position[0]
        dy = other_field.position[1] - self.position[1]
        dz = other_field.position[2] - self.position[2]
        distance = math.sqrt(dx**2 + dy**2 + dz**2)
    
        if distance < 0.01:
            distance = 0.01  # Avoid division by zero
    
        # Flow proportional to gradient / distance
        gradient_strength = (self.energy.total_energy - other_field.energy.total_energy) / distance
        energy_flow = gradient_strength * 0.05
    
        # Update gradients
        new_self_gradient = (
            self.gradient[0] - dx * 0.1,
            self.gradient[1] - dy * 0.1,
            self.gradient[2] - dz * 0.1
        )
    
        new_other_gradient = (
            other_field.gradient[0] + dx * 0.1,
            other_field.gradient[1] + dy * 0.1,
            other_field.gradient[2] + dz * 0.1
        )
    
        new_self_energy = EnergyState(
            total_energy=self.energy.total_energy - energy_flow,
            kinetic=self.energy.kinetic - energy_flow * 0.6,
            potential=self.energy.potential - energy_flow * 0.4,
            entropy=self.energy.entropy + abs(energy_flow) * 0.01,
            quantum_coherence=self.energy.quantum_coherence,
            phase_angle=self.energy.phase_angle
        )
    
        new_other_energy = EnergyState(
            total_energy=other_field.energy.total_energy + energy_flow,
            kinetic=other_field.energy.kinetic + energy_flow * 0.6,
            potential=other_field.energy.potential + energy_flow * 0.4,
            entropy=other_field.energy.entropy + abs(energy_flow) * 0.01,
            quantum_coherence=other_field.energy.quantum_coherence,
            phase_angle=other_field.energy.phase_angle
        )
    
        return (
            FieldState(self.name, new_self_energy, self.position, new_self_gradient,
                      self.capacity, self.age + 1, self.phase_state, self.frequency,
                      self.fractal_depth, self.entangled_with),
            FieldState(other_field.name, new_other_energy, other_field.position, new_other_gradient,
                      other_field.capacity, other_field.age + 1, other_field.phase_state,
                      other_field.frequency, other_field.fractal_depth, other_field.entangled_with)
        )

    def regenerate(self, input_energy: float) -> 'FieldState':
        """Regenerative process that builds capacity while processing energy"""
        # Use input energy to both do work and build capacity
        work_fraction = 0.7
        capacity_growth_fraction = 0.3
    
        work_energy = input_energy * work_fraction
        capacity_energy = input_energy * capacity_growth_fraction
    
        new_capacity = self.capacity * (1.0 + capacity_energy / 100.0)
        new_total_energy = self.energy.total_energy + work_energy
    
        # Efficiency improves with capacity
        efficiency_bonus = min(new_capacity / self.capacity - 1.0, 0.2)
    
        new_energy = EnergyState(
            total_energy=new_total_energy * (1.0 + efficiency_bonus),
            kinetic=self.energy.kinetic + work_energy * 0.6,
            potential=self.energy.potential + work_energy * 0.4,
            entropy=self.energy.entropy + input_energy * 0.005,  # Small entropy increase
            quantum_coherence=min(self.energy.quantum_coherence + 0.01, 1.0),
            phase_angle=self.energy.phase_angle
        )
    
        return FieldState(
            self.name, new_energy, self.position, self.gradient,
            new_capacity, self.age + 1, self.phase_state, self.frequency,
            self.fractal_depth, self.entangled_with
        )

    def decay(self, decay_rate: float = 0.05) -> 'FieldState':
        """Natural decay process - energy dissipates"""
        energy_loss = self.energy.total_energy * decay_rate
    
        new_energy = EnergyState(
            total_energy=self.energy.total_energy - energy_loss,
            kinetic=self.energy.kinetic * (1 - decay_rate),
            potential=self.energy.potential * (1 - decay_rate),
            entropy=self.energy.entropy + energy_loss * 0.1,  # Entropy increases
            quantum_coherence=self.energy.quantum_coherence * 0.95,  # Decoherence
            phase_angle=self.energy.phase_angle
        )
    
        return FieldState(
            self.name, new_energy, self.position, self.gradient,
            self.capacity * 0.99, self.age + 1, self.phase_state, self.frequency,
            self.fractal_depth, self.entangled_with
        )

    def directed_transfer(self, other_field, amount: float) -> Tuple['FieldState', 'FieldState']:
            """Transfer a specific amount of energy from self to other_field.
            Unlike interact_with(), this is a one-way transfer of a fixed amount,
            matching COBOL MOVE semantics. Energy is conserved: source loses
            exactly what target gains, plus a small entropy cost."""
            # Clamp to available energy
            actual_amount = min(amount, self.energy.total_energy * 0.9)  # Keep 10% minimum
            entropy_cost = actual_amount * 0.01

            new_self_energy = EnergyState(
                total_energy=self.energy.total_energy - actual_amount,
                kinetic=self.energy.kinetic - actual_amount * 0.6,
                potential=self.energy.potential - actual_amount * 0.4,
                entropy=self.energy.entropy + entropy_cost,
                quantum_coherence=self.energy.quantum_coherence * 0.99,
                phase_angle=self.energy.phase_angle
            )

            new_other_energy = EnergyState(
                total_energy=other_field.energy.total_energy + actual_amount,
                kinetic=other_field.energy.kinetic + actual_amount * 0.6,
                potential=other_field.energy.potential + actual_amount * 0.4,
                entropy=other_field.energy.entropy + entropy_cost,
                quantum_coherence=other_field.energy.quantum_coherence * 0.99,
                phase_angle=other_field.energy.phase_angle
            )

            return (
                FieldState(self.name, new_self_energy, self.position, self.gradient,
                          self.capacity, self.age + 1, self.phase_state, self.frequency,
                          self.fractal_depth, self.entangled_with),
                FieldState(other_field.name, new_other_energy, other_field.position,
                          other_field.gradient, other_field.capacity, other_field.age + 1,
                          other_field.phase_state, other_field.frequency, other_field.fractal_depth,
                          other_field.entangled_with)
            )

    def symbiosis_with(self, other_field) -> Tuple['FieldState', 'FieldState']:
        """Symbiotic relationship - both fields benefit"""
        # Each field contributes to the other's capacity growth
        self_contribution = self.energy.total_energy * 0.05
        other_contribution = other_field.energy.total_energy * 0.05
    
        # Both gain capacity, with minimal energy cost
        new_self = self.regenerate(other_contribution)
        new_other = other_field.regenerate(self_contribution)
    
        # Small energy exchange for the interaction
        energy_cost = 0.01 * (self_contribution + other_contribution)
    
        new_self.energy.total_energy -= energy_cost / 2
        new_other.energy.total_energy -= energy_cost / 2
    
        # Frequency entrainment in symbiosis
        avg_freq = (new_self.frequency + new_other.frequency) / 2
        new_self = FieldState(
            new_self.name, new_self.energy, new_self.position, new_self.gradient,
            new_self.capacity, new_self.age, new_self.phase_state, 
            avg_freq, new_self.fractal_depth, new_self.entangled_with
        )
        new_other = FieldState(
            new_other.name, new_other.energy, new_other.position, new_other.gradient,
            new_other.capacity, new_other.age, new_other.phase_state,
            avg_freq, new_other.fractal_depth, new_other.entangled_with
        )
    
        return (new_self, new_other)

class ConservationViolation(Exception):
    """Raised when energy conservation is violated"""
    pass


class COBOLBridge:
    """
    COBOL-inspired syntax bridge for the Cyclic interpreter.

    This is NOT a COBOL compiler — it uses COBOL-inspired structured syntax
    (divisions, verbs, PIC clauses) as an alternative way to express Cyclic
    field operations. Think of it as "enterprise-flavored Cyclic."

    DIVISION structure:
      IDENTIFICATION DIVISION  → Program metadata (PROGRAM-ID)
      DATA DIVISION            → Field creation via PIC clauses
      PROCEDURE DIVISION       → Operations using COBOL-inspired verbs

    PIC clause semantics (maps to Cyclic field constraints):
      PIC 9(n)    → Energy precision to n digits (max energy = 10^n - 1)
      PIC 9(n)V99 → Energy with 2 decimal places of precision
      PIC X(n)    → Unconstrained field (no energy cap)

    Paragraphs in PROCEDURE DIVISION can be defined and invoked via PERFORM.
    """

    def __init__(self, interpreter):
        self.interpreter = interpreter
        self.paragraphs = {}  # Named procedure paragraphs
        self._field_name_registry = {}  # Maps COBOL names → internal names for collision detection
        self._field_constraints = {}  # Maps internal name → {max_energy, precision}

    def _normalize_name(self, cobol_name: str) -> str:
        """Convert a COBOL-style name to internal field name, with collision detection."""
        internal = cobol_name.lower().replace('-', '_')
        if cobol_name in self._field_name_registry:
            return self._field_name_registry[cobol_name]
        # Check for collision: different COBOL name mapping to same internal name
        for existing_cobol, existing_internal in self._field_name_registry.items():
            if existing_internal == internal and existing_cobol != cobol_name:
                # Collision detected — disambiguate
                internal = f"{internal}_{len(self._field_name_registry)}"
                break
        self._field_name_registry[cobol_name] = internal
        return internal

    def _parse_pic_clause(self, pic_str: str) -> dict:
        """Parse PIC clause into field constraints.
        PIC 9(5)    → max_energy=99999, precision=0
        PIC 9(5)V99 → max_energy=99999.99, precision=2
        PIC X(n)    → unconstrained
        """
        constraints = {'max_energy': None, 'precision': 0}

        # PIC 9(n) with optional V decimal
        numeric_match = re.match(r'9\((\d+)\)(?:V(9+))?', pic_str)
        if numeric_match:
            digits = int(numeric_match.group(1))
            constraints['max_energy'] = 10 ** digits - 1
            if numeric_match.group(2):
                constraints['precision'] = len(numeric_match.group(2))
            return constraints

        # PIC 9...9 shorthand
        shorthand_match = re.match(r'(9+)(?:V(9+))?', pic_str)
        if shorthand_match:
            digits = len(shorthand_match.group(1))
            constraints['max_energy'] = 10 ** digits - 1
            if shorthand_match.group(2):
                constraints['precision'] = len(shorthand_match.group(2))
            return constraints

        # PIC X(n) — unconstrained
        return constraints

    def parse_cobol(self, cobol_source: str) -> list:
        """Parse COBOL-inspired source into a list of operations."""
        operations = []
        lines = cobol_source.split('\n')

        current_division = None
        current_section = None
        current_paragraph = None
        paragraph_body = []

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue
            line_upper = line.upper().rstrip('.')

            # COBOL comments: * in column 7, or *> anywhere
            if line_upper.startswith('*') or line_upper.startswith('*>'):
                continue

            # Track divisions
            if 'IDENTIFICATION DIVISION' in line_upper:
                self._flush_paragraph(current_paragraph, paragraph_body)
                current_division = 'identification'
                current_paragraph = None
                paragraph_body = []
                continue
            elif 'DATA DIVISION' in line_upper:
                self._flush_paragraph(current_paragraph, paragraph_body)
                current_division = 'data'
                current_paragraph = None
                paragraph_body = []
                continue
            elif 'PROCEDURE DIVISION' in line_upper:
                self._flush_paragraph(current_paragraph, paragraph_body)
                current_division = 'procedure'
                current_paragraph = None
                paragraph_body = []
                continue

            # Track sections within divisions
            if re.match(r'[\w-]+\s+SECTION', line_upper):
                current_section = line_upper.split()[0].lower().replace('-', '_')
                continue

            if current_division == 'data':
                op = self._parse_data_line(line_upper)
                if op:
                    operations.append(op)

            elif current_division == 'procedure':
                # Detect paragraph labels: a line ending with . that is just a name
                paragraph_label = re.match(r'^([\w-]+)\s*\.$', line.strip())
                if paragraph_label and not self._is_verb(line_upper):
                    # Flush previous paragraph
                    self._flush_paragraph(current_paragraph, paragraph_body)
                    current_paragraph = paragraph_label.group(1).upper()
                    paragraph_body = []
                    continue

                if current_paragraph is not None:
                    # Accumulate lines into current paragraph
                    paragraph_body.append(line_upper)
                else:
                    # Top-level procedure statement
                    op = self._parse_procedure_line(line_upper)
                    if op:
                        operations.append(op)

        # Flush last paragraph
        self._flush_paragraph(current_paragraph, paragraph_body)

        return operations

    def _flush_paragraph(self, name, body_lines):
        """Store a completed paragraph for PERFORM lookup."""
        if name and body_lines:
            self.paragraphs[name] = body_lines

    def _is_verb(self, line: str) -> bool:
        """Check if a line starts with a known COBOL verb."""
        verbs = ('MOVE', 'COMPUTE', 'PERFORM', 'ENTANGLE', 'RESONATE',
                 'TRANSITION', 'DECAY', 'SYMBIOSIS', 'DISPLAY', 'STOP')
        return any(line.startswith(v) for v in verbs)

    def _parse_data_line(self, line: str) -> dict:
        """Parse DATA DIVISION entries into field creation operations.
        PIC clause determines energy constraints."""
        field_match = re.match(
            r'(\d+)\s+([\w-]+)\s+PIC\s+(\S+)(?:\s+VALUE\s+(\d+(?:\.\d+)?))?'
            r'(?:\s+FREQUENCY\s+(\d+(?:\.\d+)?))?',
            line
        )
        if field_match:
            cobol_name = field_match.group(2)
            internal_name = self._normalize_name(cobol_name)
            pic_str = field_match.group(3)
            energy = float(field_match.group(4)) if field_match.group(4) else 50.0
            freq = float(field_match.group(5)) if field_match.group(5) else 1.0

            constraints = self._parse_pic_clause(pic_str)
            self._field_constraints[internal_name] = constraints

            # Enforce PIC constraint on initial energy
            if constraints['max_energy'] is not None:
                energy = min(energy, constraints['max_energy'])

            # Round to PIC precision
            if constraints['precision'] > 0:
                energy = round(energy, constraints['precision'])

            return {
                'type': 'cobol_field_create',
                'name': internal_name,
                'cobol_name': cobol_name,
                'energy': energy,
                'frequency': freq,
                'constraints': constraints
            }
        return None

    def _parse_procedure_line(self, line: str) -> dict:
        """Parse PROCEDURE DIVISION statements into Cyclic operations."""
        # MOVE amount FROM field TO field (directed transfer)
        move_match = re.match(
            r'MOVE\s+(\d+(?:\.\d+)?)\s+FROM\s+([\w-]+)\s+TO\s+([\w-]+)', line)
        if move_match:
            return {
                'type': 'cobol_move',
                'amount': float(move_match.group(1)),
                'source': self._normalize_name(move_match.group(2)),
                'target': self._normalize_name(move_match.group(3))
            }

        # COMPUTE field = REGENERATE energy
        compute_match = re.match(
            r'COMPUTE\s+([\w-]+)\s*=\s*REGENERATE\s+(\d+(?:\.\d+)?)', line)
        if compute_match:
            return {
                'type': 'cobol_regenerate',
                'field': self._normalize_name(compute_match.group(1)),
                'energy': float(compute_match.group(2))
            }

        # PERFORM paragraph N TIMES
        perform_times = re.match(r'PERFORM\s+([\w-]+)\s+(\d+)\s+TIMES', line)
        if perform_times:
            return {
                'type': 'cobol_perform',
                'paragraph': perform_times.group(1).upper(),
                'times': int(perform_times.group(2))
            }

        # PERFORM paragraph (single)
        perform_single = re.match(r'PERFORM\s+([\w-]+)\s*$', line)
        if perform_single:
            return {
                'type': 'cobol_perform',
                'paragraph': perform_single.group(1).upper(),
                'times': 1
            }

        # ENTANGLE field WITH field
        entangle_match = re.match(
            r'ENTANGLE\s+([\w-]+)\s+WITH\s+([\w-]+)', line)
        if entangle_match:
            return {
                'type': 'cobol_entangle',
                'fields': [
                    self._normalize_name(entangle_match.group(1)),
                    self._normalize_name(entangle_match.group(2))
                ]
            }

        # RESONATE field WITH field
        resonate_match = re.match(
            r'RESONATE\s+([\w-]+)\s+WITH\s+([\w-]+)', line)
        if resonate_match:
            return {
                'type': 'cobol_resonate',
                'fields': [
                    self._normalize_name(resonate_match.group(1)),
                    self._normalize_name(resonate_match.group(2))
                ]
            }

        # TRANSITION field TO phase
        transition_match = re.match(
            r'TRANSITION\s+([\w-]+)\s+TO\s+([\w-]+)', line)
        if transition_match:
            return {
                'type': 'cobol_phase',
                'field': self._normalize_name(transition_match.group(1)),
                'target_phase': transition_match.group(2).lower()
            }

        # DECAY field BY rate
        decay_match = re.match(
            r'DECAY\s+([\w-]+)\s+BY\s+(\d+(?:\.\d+)?)', line)
        if decay_match:
            return {
                'type': 'cobol_decay',
                'field': self._normalize_name(decay_match.group(1)),
                'rate': float(decay_match.group(2))
            }

        # SYMBIOSIS field WITH field
        symbiosis_match = re.match(
            r'SYMBIOSIS\s+([\w-]+)\s+WITH\s+([\w-]+)', line)
        if symbiosis_match:
            return {
                'type': 'cobol_symbiosis',
                'fields': [
                    self._normalize_name(symbiosis_match.group(1)),
                    self._normalize_name(symbiosis_match.group(2))
                ]
            }

        # DISPLAY field
        display_match = re.match(r'DISPLAY\s+([\w-]+)', line)
        if display_match:
            return {
                'type': 'cobol_display',
                'field': self._normalize_name(display_match.group(1))
            }

        # STOP RUN
        if line.startswith('STOP RUN'):
            return {'type': 'cobol_stop'}

        return None

    def _enforce_constraints(self, field_name: str):
        """Apply PIC-derived constraints to a field after an operation."""
        if field_name not in self._field_constraints:
            return
        if field_name not in self.interpreter.fields:
            return

        constraints = self._field_constraints[field_name]
        field = self.interpreter.fields[field_name]

        clamped = False
        energy = field.energy.total_energy

        # Cap energy to PIC max
        if constraints['max_energy'] is not None and energy > constraints['max_energy']:
            energy = float(constraints['max_energy'])
            clamped = True

        # Round to PIC precision
        if constraints['precision'] > 0:
            energy = round(energy, constraints['precision'])

        if clamped or energy != field.energy.total_energy:
            new_energy = EnergyState(
                total_energy=energy,
                kinetic=field.energy.kinetic,
                potential=field.energy.potential,
                entropy=field.energy.entropy,
                quantum_coherence=field.energy.quantum_coherence,
                phase_angle=field.energy.phase_angle
            )
            self.interpreter.fields[field_name] = FieldState(
                field.name, new_energy, field.position, field.gradient,
                field.capacity, field.age, field.phase_state, field.frequency,
                field.fractal_depth, field.entangled_with
            )

    def _execute_paragraph(self, paragraph_name: str) -> dict:
        """Execute a named paragraph's statements."""
        if paragraph_name not in self.paragraphs:
            return {'error': f'Paragraph {paragraph_name} not defined'}

        results = {}
        for line in self.paragraphs[paragraph_name]:
            op = self._parse_procedure_line(line)
            if op:
                result = self._execute_op(op)
                if result:
                    results[f"{op['type']}_{len(results)}"] = result
                if op['type'] == 'cobol_stop':
                    break
        return results

    def _execute_op(self, op: dict) -> dict:
        """Execute a single parsed operation."""
        if op['type'] == 'cobol_field_create':
            self.interpreter.create_field(
                op['name'], op['energy'], op['frequency'])
            return {
                'type': 'field_created',
                'name': op['name'],
                'energy': op['energy'],
                'frequency': op['frequency'],
                'constraints': op.get('constraints')
            }

        elif op['type'] == 'cobol_move':
            # Directed transfer: source loses amount, target gains it
            source = op['source']
            target = op['target']
            amount = op['amount']

            if source not in self.interpreter.fields:
                self.interpreter.create_field(source, 50.0)
            if target not in self.interpreter.fields:
                self.interpreter.create_field(target, 50.0)

            src_field = self.interpreter.fields[source]
            tgt_field = self.interpreter.fields[target]

            new_src, new_tgt = src_field.directed_transfer(tgt_field, amount)
            self.interpreter.fields[source] = new_src
            self.interpreter.fields[target] = new_tgt

            self._enforce_constraints(source)
            self._enforce_constraints(target)

            return {
                'type': 'directed_transfer',
                'source': source,
                'target': target,
                'amount': amount,
                'source_energy': self.interpreter.fields[source].energy.total_energy,
                'target_energy': self.interpreter.fields[target].energy.total_energy
            }

        elif op['type'] == 'cobol_regenerate':
            cyclic_expr = f"∮regenerate({op['field']}, {op['energy']})"
            result = self.interpreter.execute(cyclic_expr)
            self._enforce_constraints(op['field'])
            return result

        elif op['type'] == 'cobol_perform':
            results = {}
            for i in range(op['times']):
                sub_result = self._execute_paragraph(op['paragraph'])
                results[f"iteration_{i}"] = sub_result
            return results

        elif op['type'] == 'cobol_entangle':
            cyclic_expr = f"⊗({op['fields'][0]}, {op['fields'][1]})"
            result = self.interpreter.execute(cyclic_expr)
            return result

        elif op['type'] == 'cobol_resonate':
            cyclic_expr = f"~({op['fields'][0]} ≈ {op['fields'][1]})"
            result = self.interpreter.execute(cyclic_expr)
            for f in op['fields']:
                self._enforce_constraints(f)
            return result

        elif op['type'] == 'cobol_phase':
            cyclic_expr = f"∂phase({op['field']}, {op['target_phase']})"
            result = self.interpreter.execute(cyclic_expr)
            self._enforce_constraints(op['field'])
            return result

        elif op['type'] == 'cobol_decay':
            cyclic_expr = f"∂decay({op['field']}, {op['rate']})"
            result = self.interpreter.execute(cyclic_expr)
            return result

        elif op['type'] == 'cobol_symbiosis':
            cyclic_expr = f"∇∇({op['fields'][0]}⇄{op['fields'][1]})"
            result = self.interpreter.execute(cyclic_expr)
            for f in op['fields']:
                self._enforce_constraints(f)
            return result

        elif op['type'] == 'cobol_display':
            field_name = op['field']
            if field_name in self.interpreter.fields:
                field = self.interpreter.fields[field_name]
                constraints = self._field_constraints.get(field_name, {})
                max_e = constraints.get('max_energy', 'unlimited')
                print(f"  DISPLAY {field_name.upper().replace('_', '-')}:")
                print(f"    ENERGY     = {field.energy.total_energy:.4f}")
                print(f"    MAX-ENERGY = {max_e}")
                print(f"    ENTROPY    = {field.energy.entropy:.4f}")
                print(f"    CAPACITY   = {field.capacity:.4f}")
                print(f"    COHERENCE  = {field.energy.quantum_coherence:.4f}")
                print(f"    PHASE      = {field.phase_state}")
                return {
                    'type': 'display',
                    'field': field_name,
                    'energy': field.energy.total_energy
                }

        elif op['type'] == 'cobol_stop':
            return {'type': 'stop_run'}

        return None

    def execute_cobol(self, cobol_source: str) -> dict:
        """Parse and execute COBOL-inspired source through the Cyclic interpreter.

        After executing top-level operations, if paragraphs were defined but
        no top-level PERFORM was issued, the last defined paragraph is
        auto-executed as the entry point (standard COBOL convention).
        """
        operations = self.parse_cobol(cobol_source)
        results = {}

        has_perform = any(op['type'] == 'cobol_perform' for op in operations)
        stopped = False

        for op in operations:
            result = self._execute_op(op)
            if result:
                results[f"{op['type']}_{len(results)}"] = result
            if op['type'] == 'cobol_stop':
                stopped = True
                break

        # If paragraphs exist but no top-level PERFORM ran them,
        # auto-execute the last paragraph as the entry point
        if not stopped and not has_perform and self.paragraphs:
            last_para = list(self.paragraphs.keys())[-1]
            entry_result = self._execute_paragraph(last_para)
            results[f"entry_{last_para}"] = entry_result

        return results

class CyclicalInterpreter:
    """Main interpreter for cyclical programming language"""

    def __init__(self):
        self.fields: Dict[str, FieldState] = {}
        self.energy_budget: float = 1000.0
        self.energy_used: float = 0.0
    
    def create_field(self, name: str, initial_energy: float = 10.0, frequency: float = 1.0):
        """Create a new field with initial energy"""
        energy_state = EnergyState(total_energy=initial_energy, entropy=1.0, phase_angle=0.0)
        self.fields[name] = FieldState(name, energy_state, frequency=frequency)
    
    def parse_expression(self, expr: str) -> Dict[str, Any]:
        """Parse cyclical language expressions"""
        expr = expr.strip()
    
        # Parse quantum entanglement: ⊗(field1, field2)
        quantum_pattern = r'⊗\(([^,]+),\s*([^)]+)\)'
        match = re.match(quantum_pattern, expr)
        if match:
            return {
                'type': 'quantum_entangle',
                'fields': [match.group(1).strip(), match.group(2).strip()]
            }
    
        # Parse resonance: ~(field1 ≈ field2)
        resonance_pattern = r'~\(([^≈]+)\s*≈\s*([^)]+)\)'
        match = re.match(resonance_pattern, expr)
        if match:
            return {
                'type': 'resonance',
                'fields': [match.group(1).strip(), match.group(2).strip()]
            }
    
        # Parse phase transition: ∂phase(field, target_phase)
        phase_pattern = r'∂phase\(([^,]+),\s*([^)]+)\)'
        match = re.match(phase_pattern, expr)
        if match:
            return {
                'type': 'phase_transition',
                'field': match.group(1).strip(),
                'target_phase': match.group(2).strip()
            }
    
        # Parse fractal spawn: ∮^n(field, depth)
        fractal_pattern = r'∮\^(\d+)\(([^,]+),\s*(\d+)\)'
        match = re.match(fractal_pattern, expr)
        if match:
            return {
                'type': 'fractal_spawn',
                'iterations': int(match.group(1)),
                'field': match.group(2).strip(),
                'depth': int(match.group(3))
            }
    
        # Parse spatial gradient: ∇spatial(field1, field2)
        spatial_pattern = r'∇spatial\(([^,]+),\s*([^)]+)\)'
        match = re.match(spatial_pattern, expr)
        if match:
            return {
                'type': 'spatial_gradient',
                'fields': [match.group(1).strip(), match.group(2).strip()]
            }
    
        # Parse multi-field network: ∇³F(f1↔f2↔f3)|constraints
        multi_pattern = r'∇³F?\(([^)]+)\)\|(.+)'
        match = re.match(multi_pattern, expr)
        if match:
            fields = [f.strip() for f in match.group(1).split('↔')]
            return {
                'type': 'multi_field_network',
                'fields': fields,
                'constraints': match.group(2)
            }
    
        # Parse regenerative cycle: ∮regenerate(field, energy)
        regen_pattern = r'∮regenerate\(([^,]+),\s*(\d+(?:\.\d+)?)\)'
        match = re.match(regen_pattern, expr)
        if match:
            return {
                'type': 'regenerate',
                'field': match.group(1).strip(),
                'energy': float(match.group(2))
            }
    
        # Parse decay: ∂decay(field, rate)
        decay_pattern = r'∂decay\(([^,]+)(?:,\s*(\d+(?:\.\d+)?))?\)'
        match = re.match(decay_pattern, expr)
        if match:
            rate = float(match.group(2)) if match.group(2) else 0.05
            return {
                'type': 'decay',
                'field': match.group(1).strip(),
                'rate': rate
            }
    
        # Parse symbiosis: ∇∇(field1⇄field2) - double gradient indicates symbiosis
        symbiosis_pattern = r'∇∇\(([^⇄]+)⇄([^)]+)\)'
        match = re.match(symbiosis_pattern, expr)
        if match:
            return {
                'type': 'symbiosis',
                'fields': [match.group(1).strip(), match.group(2).strip()]
            }
    
        # Parse field interaction: ∇F(s↔w)|∂E/∂t=0
        field_pattern = r'∇(?:²)?F?\(([^)]+)\)\|(.+)'
        match = re.match(field_pattern, expr)
    
        if match:
            interaction_part = match.group(1)
            constraint_part = match.group(2)
        
            # Parse interaction (s↔w)
            if '↔' in interaction_part:
                fields = [f.strip() for f in interaction_part.split('↔')]
                return {
                    'type': 'bidirectional_interaction',
                    'fields': fields,
                    'constraints': constraint_part
                }
            elif '→' in interaction_part:
                fields = [f.strip() for f in interaction_part.split('→')]
                return {
                    'type': 'unidirectional_flow',
                    'fields': fields,
                    'constraints': constraint_part
                }
    
        # Parse COBOL-inspired inline commands: COBOL:VERB args
        cobol_inline = re.match(r'COBOL:(\w+)\s*(.*)', expr, re.IGNORECASE)
        if cobol_inline:
            verb = cobol_inline.group(1).upper()
            args = cobol_inline.group(2).strip()
            if verb == 'MOVE':
                move_match = re.match(r'(\d+(?:\.\d+)?)\s+FROM\s+([\w-]+)\s+TO\s+([\w-]+)', args, re.IGNORECASE)
                if move_match:
                    return {
                        'type': 'directed_transfer',
                        'amount': float(move_match.group(1)),
                        'source': move_match.group(2).lower().replace('-', '_'),
                        'target': move_match.group(3).lower().replace('-', '_')
                    }
            elif verb == 'COMPUTE':
                compute_match = re.match(r'([\w-]+)\s*=\s*REGENERATE\s+(\d+(?:\.\d+)?)', args, re.IGNORECASE)
                if compute_match:
                    return {
                        'type': 'regenerate',
                        'field': compute_match.group(1).lower().replace('-', '_'),
                        'energy': float(compute_match.group(2))
                    }
            elif verb == 'ENTANGLE':
                ent_match = re.match(r'([\w-]+)\s+WITH\s+([\w-]+)', args, re.IGNORECASE)
                if ent_match:
                    return {
                        'type': 'quantum_entangle',
                        'fields': [ent_match.group(1).lower().replace('-', '_'),
                                   ent_match.group(2).lower().replace('-', '_')]
                    }
            elif verb == 'RESONATE':
                res_match = re.match(r'([\w-]+)\s+WITH\s+([\w-]+)', args, re.IGNORECASE)
                if res_match:
                    return {
                        'type': 'resonance',
                        'fields': [res_match.group(1).lower().replace('-', '_'),
                                   res_match.group(2).lower().replace('-', '_')]
                    }
            elif verb == 'TRANSITION':
                trans_match = re.match(r'([\w-]+)\s+TO\s+([\w-]+)', args, re.IGNORECASE)
                if trans_match:
                    return {
                        'type': 'phase_transition',
                        'field': trans_match.group(1).lower().replace('-', '_'),
                        'target_phase': trans_match.group(2).lower()
                    }
            elif verb == 'DECAY':
                decay_match = re.match(r'([\w-]+)\s+BY\s+(\d+(?:\.\d+)?)', args, re.IGNORECASE)
                if decay_match:
                    return {
                        'type': 'decay',
                        'field': decay_match.group(1).lower().replace('-', '_'),
                        'rate': float(decay_match.group(2))
                    }
            elif verb == 'SYMBIOSIS':
                sym_match = re.match(r'([\w-]+)\s+WITH\s+([\w-]+)', args, re.IGNORECASE)
                if sym_match:
                    return {
                        'type': 'symbiosis',
                        'fields': [sym_match.group(1).lower().replace('-', '_'),
                                   sym_match.group(2).lower().replace('-', '_')]
                    }

        # Parse field creation: field_name = energy_value
        creation_pattern = r'(\w+)\s*=\s*(\d+(?:\.\d+)?)'
        match = re.match(creation_pattern, expr)
        if match:
            return {
                'type': 'field_creation',
                'name': match.group(1),
                'energy': float(match.group(2))
            }

        return {'type': 'unknown', 'expression': expr}

    def check_energy_conservation(self, initial_total: float, final_total: float):
        """Verify energy conservation law"""
        tolerance = 1e-10
        if abs(initial_total - final_total) > tolerance:
            raise ConservationViolation(
                f"Energy not conserved: {initial_total} → {final_total}, "
                f"difference: {abs(initial_total - final_total)}"
            )

    def execute_bidirectional_interaction(self, field_names: List[str]) -> Dict[str, FieldState]:
        """Execute bidirectional field interaction"""
        if len(field_names) != 2:
            raise ValueError("Bidirectional interaction requires exactly 2 fields")
    
        field1_name, field2_name = field_names
    
        # Create fields if they don't exist
        if field1_name not in self.fields:
            self.create_field(field1_name, 50.0)
        if field2_name not in self.fields:
            self.create_field(field2_name, 50.0)
        
        field1 = self.fields[field1_name]
        field2 = self.fields[field2_name]
    
        # Calculate initial energy
        initial_energy = field1.energy.total_energy + field2.energy.total_energy
    
        # Perform interaction
        new_field1, new_field2 = field1.interact_with(field2)
    
        # Calculate final energy
        final_energy = new_field1.energy.total_energy + new_field2.energy.total_energy
    
        # Check conservation
        self.check_energy_conservation(initial_energy, final_energy)
    
        # Update fields
        self.fields[field1_name] = new_field1
        self.fields[field2_name] = new_field2
    
        return {field1_name: new_field1, field2_name: new_field2}

    def execute(self, code: str) -> Dict[str, Any]:
        """Execute cyclical language code"""
        results = {}
        lines = [line.strip() for line in code.split('\n') if line.strip()]
    
        for line in lines:
            try:
                parsed = self.parse_expression(line)
            
                if parsed['type'] == 'bidirectional_interaction':
                    result = self.execute_bidirectional_interaction(parsed['fields'])
                    results[f"interaction_{len(results)}"] = {
                        'type': 'bidirectional',
                        'fields': result,
                        'energy_conserved': True
                    }
            
                elif parsed['type'] == 'regenerate':
                    field_name = parsed['field']
                    if field_name not in self.fields:
                        self.create_field(field_name, 50.0)
                
                    old_field = self.fields[field_name]
                    new_field = old_field.regenerate(parsed['energy'])
                    self.fields[field_name] = new_field
                
                    results[f"regenerate_{len(results)}"] = {
                        'type': 'regenerative',
                        'field': field_name,
                        'capacity_growth': new_field.capacity - old_field.capacity,
                        'new_capacity': new_field.capacity
                    }
            
                elif parsed['type'] == 'decay':
                    field_name = parsed['field']
                    if field_name not in self.fields:
                        continue
                
                    old_field = self.fields[field_name]
                    new_field = old_field.decay(parsed['rate'])
                    self.fields[field_name] = new_field
                
                    results[f"decay_{len(results)}"] = {
                        'type': 'decay',
                        'field': field_name,
                        'energy_lost': old_field.energy.total_energy - new_field.energy.total_energy,
                        'entropy_increase': new_field.energy.entropy - old_field.energy.entropy
                    }
            
                elif parsed['type'] == 'symbiosis':
                    field1_name, field2_name = parsed['fields']
                
                    if field1_name not in self.fields:
                        self.create_field(field1_name, 80.0)
                    if field2_name not in self.fields:
                        self.create_field(field2_name, 80.0)
                
                    field1 = self.fields[field1_name]
                    field2 = self.fields[field2_name]
                
                    new_field1, new_field2 = field1.symbiosis_with(field2)
                
                    self.fields[field1_name] = new_field1
                    self.fields[field2_name] = new_field2
                
                    results[f"symbiosis_{len(results)}"] = {
                        'type': 'symbiotic',
                        'fields': [field1_name, field2_name],
                        'mutual_benefit': True,
                        'capacity_growth': {
                            field1_name: new_field1.capacity - field1.capacity,
                            field2_name: new_field2.capacity - field2.capacity
                        }
                    }
            
                elif parsed['type'] == 'quantum_entangle':
                    field1_name, field2_name = parsed['fields']
                
                    if field1_name not in self.fields:
                        self.create_field(field1_name, 60.0)
                    if field2_name not in self.fields:
                        self.create_field(field2_name, 60.0)
                
                    field1 = self.fields[field1_name]
                    field2 = self.fields[field2_name]
                
                    new_field1, new_field2 = field1.quantum_entangle(field2)
                
                    self.fields[field1_name] = new_field1
                    self.fields[field2_name] = new_field2
                
                    results[f"quantum_{len(results)}"] = {
                        'type': 'quantum_entanglement',
                        'fields': [field1_name, field2_name],
                        'coherence': new_field1.energy.quantum_coherence,
                        'entangled': True
                    }
            
                elif parsed['type'] == 'resonance':
                    field1_name, field2_name = parsed['fields']
                
                    if field1_name not in self.fields or field2_name not in self.fields:
                        continue
                
                    field1 = self.fields[field1_name]
                    field2 = self.fields[field2_name]
                
                    old_energy = field1.energy.total_energy + field2.energy.total_energy
                
                    new_field1, new_field2 = field1.resonate_with(field2)
                
                    self.fields[field1_name] = new_field1
                    self.fields[field2_name] = new_field2
                
                    new_energy = new_field1.energy.total_energy + new_field2.energy.total_energy
                
                    results[f"resonance_{len(results)}"] = {
                        'type': 'resonance',
                        'fields': [field1_name, field2_name],
                        'amplification': new_energy / old_energy if old_energy > 0 else 1.0,
                        'phase_locked': new_field1.energy.in_phase_with(new_field2.energy)
                    }
            
                elif parsed['type'] == 'phase_transition':
                    field_name = parsed['field']
                    target_phase = parsed['target_phase']
                
                    if field_name not in self.fields:
                        continue
                
                    old_field = self.fields[field_name]
                    new_field = old_field.phase_transition(target_phase)
                    self.fields[field_name] = new_field
                
                    results[f"phase_{len(results)}"] = {
                        'type': 'phase_transition',
                        'field': field_name,
                        'old_phase': old_field.phase_state,
                        'new_phase': new_field.phase_state,
                        'energy_cost': old_field.energy.total_energy - new_field.energy.total_energy
                    }
            
                elif parsed['type'] == 'fractal_spawn':
                    field_name = parsed['field']
                    depth = parsed['depth']
                
                    if field_name not in self.fields:
                        continue
                
                    parent_field = self.fields[field_name]
                    spawns = parent_field.fractal_spawn(depth)
                
                    # Add spawns to field registry
                    for spawn in spawns:
                        self.fields[spawn.name] = spawn
                
                    results[f"fractal_{len(results)}"] = {
                        'type': 'fractal_generation',
                        'parent': field_name,
                        'depth': depth,
                        'spawns_created': len(spawns),
                        'spawn_names': [s.name for s in spawns]
                    }
            
                elif parsed['type'] == 'spatial_gradient':
                    field1_name, field2_name = parsed['fields']
                
                    if field1_name not in self.fields or field2_name not in self.fields:
                        continue
                
                    field1 = self.fields[field1_name]
                    field2 = self.fields[field2_name]
                
                    new_field1, new_field2 = field1.spatial_gradient_flow(field2)
                
                    self.fields[field1_name] = new_field1
                    self.fields[field2_name] = new_field2
                
                    results[f"spatial_{len(results)}"] = {
                        'type': 'spatial_gradient_flow',
                        'fields': [field1_name, field2_name],
                        'gradient_strength': new_field1.gradient
                    }
            
                elif parsed['type'] == 'multi_field_network':
                    field_names = parsed['fields']
                
                    # Ensure all fields exist
                    for fname in field_names:
                        if fname not in self.fields:
                            self.create_field(fname, 70.0)
                
                    # Interact all pairs in network
                    interactions = []
                    for i in range(len(field_names)):
                        for j in range(i+1, len(field_names)):
                            f1 = self.fields[field_names[i]]
                            f2 = self.fields[field_names[j]]
                        
                            new_f1, new_f2 = f1.interact_with(f2)
                        
                            self.fields[field_names[i]] = new_f1
                            self.fields[field_names[j]] = new_f2
                        
                            interactions.append((field_names[i], field_names[j]))
                
                    results[f"network_{len(results)}"] = {
                        'type': 'multi_field_network',
                        'fields': field_names,
                        'interactions': interactions,
                        'network_size': len(field_names)
                    }
                
                elif parsed['type'] == 'directed_transfer':
                    source = parsed['source']
                    target = parsed['target']
                    amount = parsed['amount']

                    if source not in self.fields:
                        self.create_field(source, 50.0)
                    if target not in self.fields:
                        self.create_field(target, 50.0)

                    src_field = self.fields[source]
                    tgt_field = self.fields[target]
                    new_src, new_tgt = src_field.directed_transfer(tgt_field, amount)
                    self.fields[source] = new_src
                    self.fields[target] = new_tgt

                    results[f"transfer_{len(results)}"] = {
                        'type': 'directed_transfer',
                        'source': source,
                        'target': target,
                        'amount': amount,
                        'source_energy': new_src.energy.total_energy,
                        'target_energy': new_tgt.energy.total_energy
                    }

                elif parsed['type'] == 'field_creation':
                    self.create_field(parsed['name'], parsed['energy'])
                    results[f"creation_{len(results)}"] = {
                        'type': 'field_created',
                        'field': parsed['name'],
                        'energy': parsed['energy']
                    }

                elif parsed['type'] == 'unknown':
                    results[f"unknown_{len(results)}"] = {
                        'type': 'unknown',
                        'expression': parsed['expression']
                    }
                
            except ConservationViolation as e:
                results[f"error_{len(results)}"] = {
                    'type': 'conservation_violation',
                    'error': str(e)
                }
            except Exception as e:
                results[f"error_{len(results)}"] = {
                    'type': 'execution_error',
                    'error': str(e)
                }
    
        return results

    def get_system_state(self) -> Dict[str, Any]:
        """Get current state of all fields and energy"""
        total_energy = sum(f.energy.total_energy for f in self.fields.values())
        total_entropy = sum(f.energy.entropy for f in self.fields.values())
        avg_capacity = sum(f.capacity for f in self.fields.values()) / len(self.fields) if self.fields else 0
        avg_coherence = sum(f.energy.quantum_coherence for f in self.fields.values()) / len(self.fields) if self.fields else 0
    
        return {
            'fields': {
                name: {
                    'energy': field.energy.total_energy,
                    'kinetic': field.energy.kinetic,
                    'potential': field.energy.potential,
                    'entropy': field.energy.entropy,
                    'quantum_coherence': field.energy.quantum_coherence,
                    'phase_angle': field.energy.phase_angle,
                    'capacity': field.capacity,
                    'age': field.age,
                    'phase_state': field.phase_state,
                    'frequency': field.frequency,
                    'fractal_depth': field.fractal_depth,
                    'entangled_with': field.entangled_with,
                    'position': field.position,
                    'gradient': field.gradient
                }
                for name, field in self.fields.items()
            },
            'total_system_energy': total_energy,
            'total_system_entropy': total_entropy,
            'average_capacity': avg_capacity,
            'average_coherence': avg_coherence,
            'energy_budget_remaining': self.energy_budget - self.energy_used
        }

    def display_state(self, show_all_fields=True):
        """Pretty print current system state"""
        state = self.get_system_state()
        print("\n" + "="*70)
        print("SYSTEM STATE")
        print("="*70)
        print(f"Total System Energy:   {state['total_system_energy']:.4f} J")
        print(f"Total System Entropy:  {state['total_system_entropy']:.4f}")
        print(f"Average Capacity:      {state['average_capacity']:.4f}")
        print(f"Average Coherence:     {state['average_coherence']:.4f}")
        print(f"Energy Budget:         {state['energy_budget_remaining']:.4f} J")
    
        if show_all_fields or len(self.fields) <= 10:
            print("\nFields:")
            print("-"*70)
            for name, field_data in state['fields'].items():
                print(f"\n  Field: {name}")
                print(f"    Energy:           {field_data['energy']:.4f} J")
                print(f"    Phase State:      {field_data['phase_state']}")
                print(f"    Frequency:        {field_data['frequency']:.2f} Hz")
                print(f"    Capacity:         {field_data['capacity']:.4f}")
                print(f"    Entropy:          {field_data['entropy']:.4f}")
                print(f"    Coherence:        {field_data['quantum_coherence']:.4f}")
                print(f"    Phase Angle:      {field_data['phase_angle']:.4f} rad")
                print(f"    Age:              {field_data['age']} cycles")
                if field_data['fractal_depth'] > 0:
                    print(f"    Fractal Depth:    {field_data['fractal_depth']}")
                if field_data['entangled_with']:
                    print(f"    Entangled with:   {field_data['entangled_with']}")
        else:
            print(f"\n{len(self.fields)} fields in system (showing summary only)")

        print("="*70 + "\n")

    def cobol_bridge(self) -> 'COBOLBridge':
        """Create a COBOL bridge for this interpreter instance"""
        return COBOLBridge(self)

def repl():
    """Interactive REPL for the Cyclical Programming Language."""
    import readline
    interpreter = CyclicalInterpreter()

    print("Cyclical Programming Language v0.1.0")
    print("Type 'help' for commands, 'quit' to exit.\n")

    while True:
        try:
            line = input("cyclic> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not line:
            continue

        cmd = line.lower()

        if cmd in ('quit', 'exit'):
            print("Goodbye.")
            break
        elif cmd == 'help':
            print("""
Commands:
  create <name> <energy> [freq]   Create a field
  state                           Show all fields
  fields                          List field names
  reset                           Clear all fields
  cobol                           Enter COBOL-inspired mode (multi-line, end with END.)
  help                            Show this help
  quit / exit                     Exit the REPL

Cyclic expressions (enter directly):
  ∇F(a↔b)|∂E/∂t=0                Bidirectional exchange
  ∮regenerate(field, energy)      Regenerative cycle
  ∂decay(field, rate)             Natural decay
  ∇∇(a⇄b)                        Symbiotic relationship
  ⊗(a, b)                         Quantum entanglement
  ~(a ≈ b)                        Resonance coupling
  ∂phase(field, state)            Phase transition
  ∮^n(field, depth)               Fractal generation
  ∇spatial(a, b)                  Spatial gradient flow
  ∇³F(a↔b↔c)|∂E/∂t=0            Multi-field network

COBOL-inspired inline (prefix with COBOL:):
  COBOL:MOVE 20 FROM a TO b      Directed energy transfer
  COBOL:ENTANGLE a WITH b        Quantum entanglement
  COBOL:COMPUTE a = REGENERATE 30
  COBOL:RESONATE a WITH b
  COBOL:DECAY a BY 0.05
  COBOL:SYMBIOSIS a WITH b
  COBOL:TRANSITION a TO plasma
""")
        elif cmd == 'state':
            if interpreter.fields:
                interpreter.display_state()
            else:
                print("No fields created yet. Use 'create <name> <energy>' to start.")
        elif cmd == 'fields':
            if interpreter.fields:
                for name, field in interpreter.fields.items():
                    print(f"  {name}: {field.energy.total_energy:.2f} J ({field.phase_state})")
            else:
                print("No fields.")
        elif cmd == 'reset':
            interpreter = CyclicalInterpreter()
            print("All fields cleared.")
        elif cmd == 'cobol':
            print("Enter COBOL-inspired program (type END. on its own line to execute):")
            cobol_lines = []
            while True:
                try:
                    cline = input("cobol> ")
                except (EOFError, KeyboardInterrupt):
                    print("\nCOBOL input cancelled.")
                    cobol_lines = []
                    break
                if cline.strip().upper() == 'END.':
                    break
                cobol_lines.append(cline)
            if cobol_lines:
                bridge = interpreter.cobol_bridge()
                try:
                    result = bridge.execute_cobol('\n'.join(cobol_lines))
                    print(f"Executed {len(result)} operations.")
                except Exception as e:
                    print(f"Error: {e}")
        elif cmd.startswith('create '):
            parts = cmd.split()
            if len(parts) < 3:
                print("Usage: create <name> <energy> [frequency]")
            else:
                name = parts[1]
                try:
                    energy = float(parts[2])
                    freq = float(parts[3]) if len(parts) > 3 else 1.0
                    interpreter.create_field(name, energy, freq)
                    print(f"Created field '{name}' with {energy} J (freq={freq} Hz)")
                except ValueError:
                    print("Energy and frequency must be numbers.")
        else:
            # Try to execute as a Cyclic expression
            try:
                result = interpreter.execute(line)
                for key, val in result.items():
                    if val.get('type') == 'unknown':
                        print(f"Unknown expression: {val.get('expression', line)}")
                    elif val.get('type') == 'conservation_violation':
                        print(f"Conservation violation: {val.get('error')}")
                    elif val.get('type') == 'execution_error':
                        print(f"Error: {val.get('error')}")
                    else:
                        # Summarize the result
                        rtype = val.get('type', '')
                        if rtype == 'directed_transfer':
                            print(f"Transferred {val['amount']} J: {val['source']} ({val['source_energy']:.2f} J) -> {val['target']} ({val['target_energy']:.2f} J)")
                        elif rtype == 'regenerative':
                            print(f"Regenerated {val['field']}: capacity {val['new_capacity']:.4f} (+{val['capacity_growth']:.4f})")
                        elif rtype == 'decay':
                            print(f"Decay {val['field']}: lost {val['energy_lost']:.4f} J, entropy +{val['entropy_increase']:.4f}")
                        elif rtype == 'quantum_entanglement':
                            print(f"Entangled {val['fields'][0]} <-> {val['fields'][1]} (coherence: {val['coherence']:.4f})")
                        elif rtype == 'resonance':
                            locked = "phase-locked" if val.get('phase_locked') else "not locked"
                            print(f"Resonance {val['fields'][0]} ~ {val['fields'][1]}: {val['amplification']:.4f}x ({locked})")
                        elif rtype == 'phase_transition':
                            print(f"Phase transition {val['field']}: {val['old_phase']} -> {val['new_phase']} (cost: {val['energy_cost']:.2f} J)")
                        elif rtype == 'fractal_generation':
                            print(f"Fractal {val['parent']}: spawned {val['spawns_created']} fields at depth {val['depth']}")
                        elif rtype in ('bidirectional', 'symbiotic', 'multi_field_network'):
                            print(f"OK: {rtype}")
                        elif rtype == 'field_created':
                            print(f"Created field '{val['field']}' with {val['energy']} J")
                        else:
                            print(f"OK: {val}")
            except Exception as e:
                print(f"Error: {e}")


def cli_main():
    """CLI entry point with argument parsing."""
    import argparse

    parser = argparse.ArgumentParser(
        prog='cyclic',
        description='Cyclical Programming Language - where code thinks in cycles'
    )
    parser.add_argument('file', nargs='?', help='Execute a .cyc or .cob file')
    parser.add_argument('--demo', action='store_true', help='Run the built-in demo')
    parser.add_argument('-e', '--execute', metavar='EXPR', help='Execute a single expression')
    parser.add_argument('--version', action='version', version='cyclic 0.1.0')

    args = parser.parse_args()

    if args.demo:
        _run_demo()
    elif args.execute:
        interp = CyclicalInterpreter()
        result = interp.execute(args.execute)
        interp.display_state()
    elif args.file:
        _run_file(args.file)
    else:
        repl()


def _run_file(filepath: str):
    """Execute a Cyclic or COBOL-inspired source file."""
    with open(filepath) as f:
        source = f.read()

    interp = CyclicalInterpreter()

    if filepath.endswith('.cob') or 'IDENTIFICATION DIVISION' in source.upper():
        print(f"Executing COBOL-inspired program: {filepath}")
        bridge = interp.cobol_bridge()
        bridge.execute_cobol(source)
    else:
        print(f"Executing Cyclic program: {filepath}")
        result = interp.execute(source)
        for key, val in result.items():
            if val.get('type') == 'execution_error':
                print(f"Error on line: {val.get('error')}")

    interp.display_state()


def _run_demo():
    """Run a quick built-in demo."""
    print("Cyclical Programming Language - Quick Demo")
    print("="*60)

    interp = CyclicalInterpreter()

    print("\n1. Creating fields...")
    interp.create_field("sun", 200.0, frequency=1.0)
    interp.create_field("planet", 100.0, frequency=2.0)
    interp.create_field("life", 50.0, frequency=4.0)

    print("2. Energy exchange: sun <-> planet")
    interp.execute("∇F(sun↔planet)|∂E/∂t=0")

    print("3. Life regenerates")
    interp.execute("∮regenerate(life, 30)")

    print("4. Quantum entangle planet and life")
    interp.execute("⊗(planet, life)")

    print("5. Resonance: planet ~ life")
    interp.execute("~(planet ≈ life)")

    print("6. Symbiosis: planet <=> life")
    interp.execute("∇∇(planet⇄life)")

    print("7. Star decays")
    interp.execute("∂decay(sun, 0.05)")

    print("\nFinal system state:")
    interp.display_state()

    state = interp.get_system_state()
    print(f"Total Energy:     {state['total_system_energy']:.2f} J")
    print(f"Total Entropy:    {state['total_system_entropy']:.2f}")
    print(f"Avg Coherence:    {state['average_coherence']:.4f}")
    print(f"Avg Capacity:     {state['average_capacity']:.4f}")
    print("="*60)


if __name__ == "__main__":
    cli_main()
