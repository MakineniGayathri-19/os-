# UNIX Operating System Process Scheduling Simulation
### Round Robin Time Slicing & Multilevel Feedback Queue (MLFQ)

---

## 📌 Project Overview
This project simulates the classic process scheduling mechanism utilized in UNIX operating systems: **Round Robin Time Slicing with Multilevel Feedback Queues (MLFQ)**.

The simulation compares process behavior under two distinct burst time conditions with random arrival times:
1. **Fixed Burst Times** (Deterministic CPU requirement across all processes).
2. **Variable (Randomized) Burst Times** (Dynamic, heterogeneous CPU workloads).

The processes run for a **fixed duration of simulation time** ($T_{\text{sim}}$), evaluating real-time system performance and calculating the **Average Waiting Time (AWT)** and **Average Turnaround Time (TAT)** for all processes completed within the time window.

---

## ⚙️ Core Parameters & Assumptions
- **Time Slice (Quantum $q$):** $3$ time units.
- **Arrival Distribution:** Random arrivals modeled via uniform distribution $t_{\text{arrival}} \in [0, T_{\text{arrival\_max}}]$.
- **Scheduling Discipline:**
  1. **Standard Round Robin (RR):** Preemptive FIFO ready queue with quantum $q = 3$.
  2. **UNIX Multilevel Feedback Queue (MLFQ):**
     - **Queue 0 (High Priority):** Time slice $q_0 = 3$. Newly arrived processes enter here.
     - **Queue 1 (Medium Priority):** Time slice $q_1 = 6$ ($2 \times q$).
     - **Queue 2 (Low Priority):** Time slice $q_2 = 12$ ($4 \times q$).
     - **Demotion Rule:** If a process exhausts its full time slice without completing, it is demoted to the next lower priority queue.
     - **Aging Mechanism:** Periodic priority boosting prevents starvation of long-running, CPU-bound processes.
- **Fixed Simulation Time Limit:** Simulation clock runs up to $T_{\text{sim}} = 60$ units (customizable).
- **Completion Filter:** Only processes that reach $0$ remaining burst time within $T_{\text{sim}}$ are factored into completed AWT & TAT.

---

## 🏗️ Process Control Block (PCB) Structure
Each process is represented by a UNIX PCB containing:
- `pid`: Unique Process Identifier.
- `name`: Process label (`P1`, `P2`, ...).
- `arrival_time`: Random arrival timestamp.
- `burst_time`: Total CPU execution time required.
- `remaining_time`: Unexecuted CPU time remaining.
- `current_queue`: Active priority queue level ($0, 1, 2$).
- `state`: Process life-cycle state (`NEW`, `READY`, `RUNNING`, `TERMINATED`, `INCOMPLETE`).
- `start_time`: First CPU dispatch timestamp (for Response Time).
- `completion_time`: Timestamp at which process finishes execution.
- `waiting_time`: Total duration spent waiting in ready queue(s).
- `turnaround_time`: Total time from arrival to termination.
- `response_time`: Initial delay between arrival and first execution.

---

## 📊 Performance Formulas
For completed processes $P_{\text{completed}}$:

$$\text{Turnaround Time (TAT)} = \text{Completion Time} - \text{Arrival Time}$$

$$\text{Waiting Time (WT)} = \text{Turnaround Time} - \text{Burst Time}$$

$$\text{Average Turnaround Time (ATAT)} = \frac{1}{|P_{\text{completed}}|} \sum_{p \in P_{\text{completed}}} \text{TAT}_p$$

$$\text{Average Waiting Time (AWT)} = \frac{1}{|P_{\text{completed}}|} \sum_{p \in P_{\text{completed}}} \text{WT}_p$$

$$\text{CPU Utilization} = \frac{\text{Total CPU Busy Time}}{\text{Total Elapsed Simulation Time}} \times 100\%$$

$$\text{Throughput} = \frac{|P_{\text{completed}}|}{\text{Total Elapsed Simulation Time}}$$

---

## 🚀 How to Run the Code

### Option 1: Python Simulation (Recommended for Visuals & Charts)
The Python simulator outputs ASCII tables, ASCII Gantt charts, summary CSV, and high-resolution comparison graphs (`comparison_metrics.png` and `gantt_chart.png`).

```bash
# Run with default parameters (12 processes, 60 time units, time slice = 3)
python3 simulate.py

# Custom parameters example:
python3 simulate.py --processes 15 --sim-time 80 --time-slice 3 --fixed-burst 6
```

#### Generated Artifacts:
- `simulation_summary.csv`: Tabular numerical data ready to import into Excel or Google Sheets.
- `comparison_metrics.png`: 4-panel comparison bar charts (AWT, ATAT, Completed Count, CPU Utilization).
- `gantt_chart.png`: Timeline visual Gantt chart showing exact process execution slices.

---

### Option 2: C Implementation (C99 Standard)
A clean, standalone C implementation is included for standard OS lab grading.

```bash
# Compile with GCC or Clang
gcc -Wall -Wextra main.c -o scheduler_c

# Run the simulation
./scheduler_c

# Or with custom arguments: ./scheduler_c [num_processes] [sim_time] [time_slice]
./scheduler_c 12 60 3
```

---

## 📈 Key Findings & Presentation Summary

| Algorithm | Burst Mode | Completed | Avg Waiting Time | Avg Turnaround Time | CPU Utilization |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Round Robin (RR)** | **Fixed Burst** | 8 / 12 | ~22.2 - 25.7 units | ~28.2 - 31.7 units | 100.0% |
| **Round Robin (RR)** | **Variable Burst** | 7 / 12 | ~18.0 - 22.1 units | ~25.0 - 27.0 units | ~98.3 - 100% |
| **UNIX MLFQ** | **Fixed Burst** | 8 / 12 | ~28.2 - 37.0 units | ~34.2 - 43.0 units | 100.0% |
| **UNIX MLFQ** | **Variable Burst** | 5-6 / 12 | ~22.0 - 23.5 units | ~27.4 - 27.6 units | ~98.3 - 100% |

### Theoretical Observations for Group Discussion / PPT:
1. **Shorter Jobs Benefit Under Variable Bursts:** When burst times are randomized, short I/O-like or quick processes complete rapidly within the first 1-2 quanta ($q=3$), significantly reducing their waiting times.
2. **Fixed Burst Predictability:** Fixed bursts result in fair, uniform progress across all processes, but turnaround times scale steadily because processes share the CPU evenly and complete near each other.
3. **MLFQ Favoring Interactive / Short Processes:** In UNIX MLFQ, short processes finish in Queue 0 ($q=3$) without ever being demoted, achieving superior response times, while CPU-bound processes drop down to Queues 1 & 2 where they receive larger time slices.
4. **Impact of Fixed Simulation Time:** Processes arriving late in the simulation window cannot finish before $T_{\text{sim}}$, highlighting the importance of evaluating completed throughput vs. incomplete queue buildup.
