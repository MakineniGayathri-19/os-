"""
UNIX Process Scheduling Simulator: Round Robin with Multilevel Feedback Queue (MLFQ)
Simulates Process Control Blocks (PCBs) with random arrivals, fixed vs. variable burst times,
and calculates Average Waiting Time (AWT) and Average Turnaround Time (TAT) for completed processes.
"""

import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum


class ProcessState(Enum):
    NEW = "NEW"
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    TERMINATED = "TERMINATED"
    INCOMPLETE = "INCOMPLETE"  # Not finished when simulation time ends


@dataclass
class PCB:
    """Process Control Block representing UNIX process metadata."""
    pid: int
    name: str
    arrival_time: int
    burst_time: int
    remaining_time: int
    priority: int = 0             # 0 = Highest priority
    current_queue: int = 0        # Queue level in MLFQ
    state: ProcessState = ProcessState.NEW
    
    # Timing and performance metrics
    start_time: Optional[int] = None
    completion_time: Optional[int] = None
    waiting_time: int = 0
    turnaround_time: int = 0
    response_time: int = 0
    cpu_cycles_used: int = 0      # Cycles used in current quantum / epoch
    
    def copy(self) -> 'PCB':
        """Deep copy PCB for fair multi-algorithm comparisons on identical workload."""
        return PCB(
            pid=self.pid,
            name=self.name,
            arrival_time=self.arrival_time,
            burst_time=self.burst_time,
            remaining_time=self.burst_time,
            priority=self.priority,
            current_queue=self.current_queue,
            state=ProcessState.NEW
        )


@dataclass
class GanttSlice:
    """Represents a discrete time interval on the CPU."""
    pid: int
    name: str
    start_time: int
    end_time: int
    queue_level: int = 0
    is_idle: bool = False


@dataclass
class SimulationResult:
    """Encapsulates all results, metrics, and logs for a simulation run."""
    algorithm_name: str
    burst_mode: str  # "Fixed" or "Variable"
    time_slice: int
    max_simulation_time: int
    all_processes: List[PCB]
    completed_processes: List[PCB]
    incomplete_processes: List[PCB]
    gantt_chart: List[GanttSlice]
    total_cpu_busy_time: int
    total_idle_time: int
    
    @property
    def avg_waiting_time(self) -> float:
        if not self.completed_processes:
            return 0.0
        return sum(p.waiting_time for p in self.completed_processes) / len(self.completed_processes)
    
    @property
    def avg_turnaround_time(self) -> float:
        if not self.completed_processes:
            return 0.0
        return sum(p.turnaround_time for p in self.completed_processes) / len(self.completed_processes)
    
    @property
    def avg_response_time(self) -> float:
        started = [p for p in self.all_processes if p.start_time is not None]
        if not started:
            return 0.0
        return sum(p.response_time for p in started) / len(started)
    
    @property
    def cpu_utilization(self) -> float:
        total_time = self.total_cpu_busy_time + self.total_idle_time
        if total_time == 0:
            return 0.0
        return (self.total_cpu_busy_time / total_time) * 100.0
    
    @property
    def throughput(self) -> float:
        total_time = self.total_cpu_busy_time + self.total_idle_time
        if total_time == 0:
            return 0.0
        return len(self.completed_processes) / total_time


def generate_processes(
    num_processes: int,
    burst_mode: str = "fixed",
    fixed_burst: int = 6,
    min_burst: int = 2,
    max_burst: int = 14,
    max_arrival_time: int = 30,
    seed: Optional[int] = 42
) -> List[PCB]:
    """
    Generates processes (PCBs) arriving at random times.
    
    Args:
        num_processes: Number of processes to generate.
        burst_mode: 'fixed' or 'variable'.
        fixed_burst: Burst time if mode is 'fixed'.
        min_burst: Minimum burst time if mode is 'variable'.
        max_burst: Maximum burst time if mode is 'variable'.
        max_arrival_time: Random arrivals will be uniformly chosen in [0, max_arrival_time].
        seed: Random seed for reproducibility.
    """
    if seed is not None:
        random.seed(seed)
        
    processes = []
    # Generate random arrivals
    arrival_times = [random.randint(0, max_arrival_time) for _ in range(num_processes)]
    # Sort arrival times so initial numbering has a logical order
    arrival_times.sort()
    
    for i in range(num_processes):
        pid = i + 1
        name = f"P{pid}"
        arrival = arrival_times[i]
        
        if burst_mode.lower() == "fixed":
            burst = fixed_burst
        else:
            burst = random.randint(min_burst, max_burst)
            
        pcb = PCB(
            pid=pid,
            name=name,
            arrival_time=arrival,
            burst_time=burst,
            remaining_time=burst
        )
        processes.append(pcb)
        
    return processes


class RoundRobinScheduler:
    """
    Standard Round Robin Scheduler with time slicing.
    Processes are placed into a single FIFO ready queue and given a time slice (quantum = 3).
    Preempted processes are placed at the tail of the ready queue.
    """
    def __init__(self, time_slice: int = 3, max_time: int = 100):
        self.time_slice = time_slice
        self.max_time = max_time
        
    def run(self, processes: List[PCB], burst_mode: str = "Fixed") -> SimulationResult:
        # Clone processes to avoid mutating originals
        proc_list = [p.copy() for p in processes]
        unstarted = sorted(proc_list, key=lambda p: (p.arrival_time, p.pid))
        
        ready_queue: List[PCB] = []
        gantt: List[GanttSlice] = []
        
        current_time = 0
        total_busy_time = 0
        total_idle_time = 0
        
        while current_time < self.max_time:
            # Check for newly arrived processes up to current_time
            while unstarted and unstarted[0].arrival_time <= current_time:
                arrived_proc = unstarted.pop(0)
                arrived_proc.state = ProcessState.READY
                ready_queue.append(arrived_proc)
                
            if not ready_queue:
                # CPU is idle until next process arrives or max_time is reached
                if unstarted:
                    next_arrival = unstarted[0].arrival_time
                    idle_duration = min(next_arrival - current_time, self.max_time - current_time)
                    if idle_duration > 0:
                        gantt.append(GanttSlice(
                            pid=-1,
                            name="IDLE",
                            start_time=current_time,
                            end_time=current_time + idle_duration,
                            is_idle=True
                        ))
                        current_time += idle_duration
                        total_idle_time += idle_duration
                    continue
                else:
                    # No more processes will arrive, fill remaining time as idle or finish
                    remaining_sim = self.max_time - current_time
                    if remaining_sim > 0:
                        gantt.append(GanttSlice(
                            pid=-1,
                            name="IDLE",
                            start_time=current_time,
                            end_time=self.max_time,
                            is_idle=True
                        ))
                        total_idle_time += remaining_sim
                        current_time = self.max_time
                    break
                    
            # Pick next process from Ready Queue
            proc = ready_queue.pop(0)
            proc.state = ProcessState.RUNNING
            
            if proc.start_time is None:
                proc.start_time = current_time
                proc.response_time = current_time - proc.arrival_time
                
            # Compute execution slice
            max_executable = self.max_time - current_time
            exec_time = min(proc.remaining_time, self.time_slice, max_executable)
            
            slice_start = current_time
            slice_end = current_time + exec_time
            
            gantt.append(GanttSlice(
                pid=proc.pid,
                name=proc.name,
                start_time=slice_start,
                end_time=slice_end,
                queue_level=0,
                is_idle=False
            ))
            
            proc.remaining_time -= exec_time
            proc.cpu_cycles_used += exec_time
            current_time = slice_end
            total_busy_time += exec_time
            
            # Enqueue any new processes that arrived during this time slice
            while unstarted and unstarted[0].arrival_time <= current_time:
                arrived_proc = unstarted.pop(0)
                arrived_proc.state = ProcessState.READY
                ready_queue.append(arrived_proc)
                
            if proc.remaining_time == 0:
                # Process completed!
                proc.completion_time = current_time
                proc.turnaround_time = proc.completion_time - proc.arrival_time
                proc.waiting_time = proc.turnaround_time - proc.burst_time
                proc.state = ProcessState.TERMINATED
            else:
                # If simulation time limit reached
                if current_time >= self.max_time:
                    proc.state = ProcessState.INCOMPLETE
                else:
                    proc.state = ProcessState.READY
                    ready_queue.append(proc)
                    
        # Any remaining processes that never finished are marked INCOMPLETE
        completed = []
        incomplete = []
        for p in proc_list:
            if p.remaining_time == 0 and p.completion_time is not None and p.completion_time <= self.max_time:
                p.state = ProcessState.TERMINATED
                completed.append(p)
            else:
                p.state = ProcessState.INCOMPLETE
                # Estimated waiting time so far
                if p.start_time is not None:
                    p.waiting_time = (self.max_time - p.arrival_time) - (p.burst_time - p.remaining_time)
                else:
                    p.waiting_time = max(0, self.max_time - p.arrival_time)
                incomplete.append(p)
                
        return SimulationResult(
            algorithm_name="Round Robin (RR)",
            burst_mode=burst_mode,
            time_slice=self.time_slice,
            max_simulation_time=self.max_time,
            all_processes=proc_list,
            completed_processes=completed,
            incomplete_processes=incomplete,
            gantt_chart=gantt,
            total_cpu_busy_time=total_busy_time,
            total_idle_time=total_idle_time
        )


class UnixMLFQScheduler:
    """
    UNIX-Style Multilevel Feedback Queue (MLFQ) with Round Robin Time Slicing.
    
    Architecture:
    - Queue 0: Highest priority, RR with quantum = time_slice (e.g. 3). All new processes enter here.
    - Queue 1: Medium priority, RR with quantum = 2 * time_slice (e.g. 6).
    - Queue 2: Lowest priority, RR with quantum = 4 * time_slice (e.g. 12) or FCFS.
    
    Feedback Rules:
    - If a process exhausts its full time slice in Queue i, it is demoted to Queue min(i+1, max_level).
    - If a process finishes early, it departs.
    - Aging mechanism: Every 'aging_interval' time units, processes waiting in lower queues are boosted
      to prevent starvation (standard UNIX priority decay/aging principle).
    """
    def __init__(
        self,
        base_time_slice: int = 3,
        num_queues: int = 3,
        max_time: int = 100,
        aging_interval: int = 24
    ):
        self.base_time_slice = base_time_slice
        self.num_queues = num_queues
        self.max_time = max_time
        self.aging_interval = aging_interval
        
        # Time quantums for each queue level: e.g. Q0: 3, Q1: 6, Q2: 12
        self.quantums = [base_time_slice * (2 ** i) for i in range(num_queues)]
        
    def run(self, processes: List[PCB], burst_mode: str = "Fixed") -> SimulationResult:
        proc_list = [p.copy() for p in processes]
        unstarted = sorted(proc_list, key=lambda p: (p.arrival_time, p.pid))
        
        queues: List[List[PCB]] = [[] for _ in range(self.num_queues)]
        gantt: List[GanttSlice] = []
        
        current_time = 0
        total_busy_time = 0
        total_idle_time = 0
        last_aging_time = 0
        
        while current_time < self.max_time:
            # Check for new arrivals up to current_time -> add to Queue 0
            while unstarted and unstarted[0].arrival_time <= current_time:
                arrived_proc = unstarted.pop(0)
                arrived_proc.state = ProcessState.READY
                arrived_proc.current_queue = 0
                queues[0].append(arrived_proc)
                
            # Check aging / priority boost
            if self.aging_interval > 0 and (current_time - last_aging_time) >= self.aging_interval:
                # Boost waiting processes in lower queues to higher queue
                for q_idx in range(1, self.num_queues):
                    while queues[q_idx]:
                        boosted = queues[q_idx].pop(0)
                        boosted.current_queue = max(0, q_idx - 1)
                        queues[boosted.current_queue].append(boosted)
                last_aging_time = current_time
                
            # Find highest priority non-empty queue
            active_q_idx = -1
            for q_idx in range(self.num_queues):
                if queues[q_idx]:
                    active_q_idx = q_idx
                    break
                    
            if active_q_idx == -1:
                # CPU is idle
                if unstarted:
                    next_arrival = unstarted[0].arrival_time
                    idle_duration = min(next_arrival - current_time, self.max_time - current_time)
                    if idle_duration > 0:
                        gantt.append(GanttSlice(
                            pid=-1,
                            name="IDLE",
                            start_time=current_time,
                            end_time=current_time + idle_duration,
                            is_idle=True
                        ))
                        current_time += idle_duration
                        total_idle_time += idle_duration
                    continue
                else:
                    remaining_sim = self.max_time - current_time
                    if remaining_sim > 0:
                        gantt.append(GanttSlice(
                            pid=-1,
                            name="IDLE",
                            start_time=current_time,
                            end_time=self.max_time,
                            is_idle=True
                        ))
                        total_idle_time += remaining_sim
                        current_time = self.max_time
                    break
                    
            # Pick process from the highest priority non-empty queue
            proc = queues[active_q_idx].pop(0)
            proc.state = ProcessState.RUNNING
            
            if proc.start_time is None:
                proc.start_time = current_time
                proc.response_time = current_time - proc.arrival_time
                
            # Queue quantum
            quantum = self.quantums[active_q_idx]
            max_executable = self.max_time - current_time
            exec_time = min(proc.remaining_time, quantum, max_executable)
            
            slice_start = current_time
            slice_end = current_time + exec_time
            
            gantt.append(GanttSlice(
                pid=proc.pid,
                name=proc.name,
                start_time=slice_start,
                end_time=slice_end,
                queue_level=active_q_idx,
                is_idle=False
            ))
            
            proc.remaining_time -= exec_time
            proc.cpu_cycles_used += exec_time
            current_time = slice_end
            total_busy_time += exec_time
            
            # Admit newly arrived processes during this execution window
            while unstarted and unstarted[0].arrival_time <= current_time:
                arrived_proc = unstarted.pop(0)
                arrived_proc.state = ProcessState.READY
                arrived_proc.current_queue = 0
                queues[0].append(arrived_proc)
                
            if proc.remaining_time == 0:
                # Finished
                proc.completion_time = current_time
                proc.turnaround_time = proc.completion_time - proc.arrival_time
                proc.waiting_time = proc.turnaround_time - proc.burst_time
                proc.state = ProcessState.TERMINATED
            else:
                if current_time >= self.max_time:
                    proc.state = ProcessState.INCOMPLETE
                else:
                    # Demote to lower queue (feedback mechanism)
                    next_q = min(active_q_idx + 1, self.num_queues - 1)
                    proc.current_queue = next_q
                    proc.state = ProcessState.READY
                    queues[next_q].append(proc)
                    
        # Summarize completed and incomplete
        completed = []
        incomplete = []
        for p in proc_list:
            if p.remaining_time == 0 and p.completion_time is not None and p.completion_time <= self.max_time:
                p.state = ProcessState.TERMINATED
                completed.append(p)
            else:
                p.state = ProcessState.INCOMPLETE
                if p.start_time is not None:
                    p.waiting_time = (self.max_time - p.arrival_time) - (p.burst_time - p.remaining_time)
                else:
                    p.waiting_time = max(0, self.max_time - p.arrival_time)
                incomplete.append(p)
                
        return SimulationResult(
            algorithm_name="UNIX Multilevel Feedback Queue (MLFQ)",
            burst_mode=burst_mode,
            time_slice=self.base_time_slice,
            max_simulation_time=self.max_time,
            all_processes=proc_list,
            completed_processes=completed,
            incomplete_processes=incomplete,
            gantt_chart=gantt,
            total_cpu_busy_time=total_busy_time,
            total_idle_time=total_idle_time
        )
