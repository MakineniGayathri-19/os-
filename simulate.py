#!/usr/bin/env python3
"""
CLI Runner and Visualizer for UNIX Round Robin & MLFQ Simulation
Simulates Fixed vs Variable Burst times with random arrivals and time slice = 3 units.
Outputs ASCII tables, detailed metrics, and plots for group presentation.
"""

import os
import sys
import argparse
import csv
from typing import List
from scheduler import (
    PCB,
    ProcessState,
    SimulationResult,
    RoundRobinScheduler,
    UnixMLFQScheduler,
    generate_processes
)

try:
    import matplotlib
    matplotlib.use('Agg')  # Headless mode for clean script execution
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


def print_banner(text: str):
    width = 80
    print("\n" + "=" * width)
    print(f"{text.center(width)}")
    print("=" * width)


def print_section(text: str):
    print("\n" + "-" * 80)
    print(f" >>> {text}")
    print("-" * 80)


def format_table(headers: List[str], rows: List[List[str]]) -> str:
    """Renders a clean ASCII table."""
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(val)))
            
    header_line = " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    sep_line = "-+-".join("-" * col_widths[i] for i in range(len(headers)))
    
    table_lines = [header_line, sep_line]
    for row in rows:
        table_lines.append(" | ".join(str(val).ljust(col_widths[i]) for i, val in enumerate(row)))
    return "\n".join(table_lines)


def print_process_table(result: SimulationResult):
    headers = [
        "PID", "Arrival", "Burst", "Remaining", "Finish", "Turnaround", "Waiting", "Response", "State"
    ]
    rows = []
    # Sort by PID
    sorted_procs = sorted(result.all_processes, key=lambda p: p.pid)
    for p in sorted_procs:
        finish = str(p.completion_time) if p.completion_time is not None else "-"
        tat = str(p.turnaround_time) if p.completion_time is not None else "-"
        state_str = p.state.value
        rows.append([
            p.name,
            str(p.arrival_time),
            str(p.burst_time),
            str(p.remaining_time),
            finish,
            tat,
            str(p.waiting_time),
            str(p.response_time),
            state_str
        ])
    print(format_table(headers, rows))


def print_metrics_summary(result: SimulationResult):
    print("\n--- Key Performance Metrics ---")
    print(f"Algorithm                  : {result.algorithm_name}")
    print(f"Burst Mode                 : {result.burst_mode}")
    print(f"Time Slice (Quantum)       : {result.time_slice} units")
    print(f"Fixed Simulation Duration  : {result.max_simulation_time} units")
    print(f"Total Processes Generated  : {len(result.all_processes)}")
    print(f"Completed Processes        : {len(result.completed_processes)} ({len(result.completed_processes)/len(result.all_processes)*100:.1f}%)")
    print(f"Incomplete Processes       : {len(result.incomplete_processes)}")
    print(f"Average Turnaround Time    : {result.avg_turnaround_time:.2f} units (Completed only)")
    print(f"Average Waiting Time       : {result.avg_waiting_time:.2f} units (Completed only)")
    print(f"Average Response Time      : {result.avg_response_time:.2f} units")
    print(f"CPU Utilization            : {result.cpu_utilization:.2f}% (Busy: {result.total_cpu_busy_time}, Idle: {result.total_idle_time})")
    print(f"Throughput                 : {result.throughput:.4f} processes/unit time")


def print_ascii_gantt(result: SimulationResult, max_display_slices: int = 35):
    print("\n--- ASCII Execution Timeline (Gantt Chart) ---")
    slices = result.gantt_chart
    if not slices:
        print("[No execution recorded]")
        return
        
    display_slices = slices[:max_display_slices]
    
    # Top bar
    bar_top = ""
    timeline = ""
    
    current_t = 0
    for s in display_slices:
        name = s.name if not s.is_idle else "IDLE"
        duration = s.end_time - s.start_time
        width = max(len(name) + 2, duration * 2)
        cell = f"[{name:^{width-2}}]"
        bar_top += cell
        # Time markers
        t_str = str(s.start_time)
        timeline += t_str + " " * (len(cell) - len(t_str))
        current_t = s.end_time
        
    timeline += str(current_t)
    
    print(bar_top)
    print(timeline)
    if len(slices) > max_display_slices:
        print(f"... and {len(slices) - max_display_slices} more slices (truncated for display, see graphical chart)")


def export_csv_summary(results: List[SimulationResult], filepath: str = "simulation_summary.csv"):
    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Algorithm", "Burst_Mode", "Time_Slice", "Sim_Time",
            "Total_Processes", "Completed_Processes", "Incomplete_Processes",
            "Avg_Waiting_Time", "Avg_Turnaround_Time", "Avg_Response_Time",
            "CPU_Utilization_Pct", "Throughput"
        ])
        for r in results:
            writer.writerow([
                r.algorithm_name,
                r.burst_mode,
                r.time_slice,
                r.max_simulation_time,
                len(r.all_processes),
                len(r.completed_processes),
                len(r.incomplete_processes),
                f"{r.avg_waiting_time:.2f}",
                f"{r.avg_turnaround_time:.2f}",
                f"{r.avg_response_time:.2f}",
                f"{r.cpu_utilization:.2f}",
                f"{r.throughput:.4f}"
            ])
    print(f"\n[INFO] Summary exported to CSV: {filepath}")


def plot_comparison_graphs(results: List[SimulationResult], output_path: str = "comparison_metrics.png"):
    if not HAS_MATPLOTLIB:
        print("[WARN] matplotlib not available, skipping graphical plot export.")
        return
        
    labels = [f"{r.algorithm_name}\n({r.burst_mode})" for r in results]
    awt = [r.avg_waiting_time for r in results]
    atat = [r.avg_turnaround_time for r in results]
    completed = [len(r.completed_processes) for r in results]
    cpu_util = [r.cpu_utilization for r in results]
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("UNIX Scheduling Simulation: Fixed vs. Variable Burst Times\n(Time Slice = 3 units)", fontsize=16, fontweight='bold')
    
    colors = ['#2b5c8f', '#4682b4', '#d95f02', '#7570b3']
    
    # Plot 1: Average Waiting Time
    ax1 = axes[0, 0]
    bars1 = ax1.bar(labels, awt, color=colors[:len(labels)], width=0.55, edgecolor='black', alpha=0.85)
    ax1.set_title("Average Waiting Time (Completed Processes)", fontweight='bold')
    ax1.set_ylabel("Time Units")
    ax1.grid(axis='y', linestyle='--', alpha=0.7)
    for bar in bars1:
        yval = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2.0, yval + 0.3, f"{yval:.2f}", ha='center', va='bottom', fontweight='bold')
        
    # Plot 2: Average Turnaround Time
    ax2 = axes[0, 1]
    bars2 = ax2.bar(labels, atat, color=colors[:len(labels)], width=0.55, edgecolor='black', alpha=0.85)
    ax2.set_title("Average Turnaround Time (Completed Processes)", fontweight='bold')
    ax2.set_ylabel("Time Units")
    ax2.grid(axis='y', linestyle='--', alpha=0.7)
    for bar in bars2:
        yval = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2.0, yval + 0.3, f"{yval:.2f}", ha='center', va='bottom', fontweight='bold')
        
    # Plot 3: Completed Processes Count
    ax3 = axes[1, 0]
    bars3 = ax3.bar(labels, completed, color=colors[:len(labels)], width=0.55, edgecolor='black', alpha=0.85)
    ax3.set_title("Completed Processes Count (Within Fixed Time)", fontweight='bold')
    ax3.set_ylabel("Number of Processes")
    ax3.grid(axis='y', linestyle='--', alpha=0.7)
    for bar in bars3:
        yval = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width()/2.0, yval + 0.2, f"{int(yval)}", ha='center', va='bottom', fontweight='bold')
        
    # Plot 4: CPU Utilization
    ax4 = axes[1, 1]
    bars4 = ax4.bar(labels, cpu_util, color=colors[:len(labels)], width=0.55, edgecolor='black', alpha=0.85)
    ax4.set_title("CPU Utilization (%)", fontweight='bold')
    ax4.set_ylabel("Percentage (%)")
    ax4.set_ylim(0, 105)
    ax4.grid(axis='y', linestyle='--', alpha=0.7)
    for bar in bars4:
        yval = bar.get_height()
        ax4.text(bar.get_x() + bar.get_width()/2.0, yval + 1.0, f"{yval:.1f}%", ha='center', va='bottom', fontweight='bold')
        
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"[INFO] High-resolution metrics chart saved: {output_path}")


def plot_gantt_chart(results: List[SimulationResult], output_path: str = "gantt_chart.png"):
    """Generates a visual timeline Gantt chart for the runs."""
    if not HAS_MATPLOTLIB:
        return
        
    fig, axes = plt.subplots(len(results), 1, figsize=(15, 3.2 * len(results)), sharex=True)
    if len(results) == 1:
        axes = [axes]
        
    fig.suptitle("Process Execution Timeline (Gantt Chart)\n[Fixed Time Simulation]", fontsize=14, fontweight='bold')
    
    # Palette for processes
    cmap = plt.get_cmap('tab20')
    
    for idx, (ax, res) in enumerate(zip(axes, results)):
        ax.set_title(f"{res.algorithm_name} - {res.burst_mode} Burst Time (Quantum = {res.time_slice})", fontsize=11, fontweight='bold')
        ax.set_ylim(0, 10)
        ax.set_yticks([])
        ax.set_xlim(0, res.max_simulation_time)
        ax.grid(axis='x', linestyle=':', alpha=0.6)
        
        for s in res.gantt_chart:
            dur = s.end_time - s.start_time
            if s.is_idle:
                color = '#cccccc'
                text_label = "IDLE"
            else:
                color = cmap((s.pid * 3) % 20)
                text_label = s.name
                
            rect = patches.Rectangle((s.start_time, 2), dur, 6, linewidth=1, edgecolor='black', facecolor=color, alpha=0.9)
            ax.add_patch(rect)
            
            # Label
            if dur >= 2:
                ax.text(s.start_time + dur / 2.0, 5, text_label, ha='center', va='center', fontsize=8, fontweight='bold', color='black' if s.is_idle else 'white')
                
        ax.set_ylabel("CPU", fontsize=10)
        
    axes[-1].set_xlabel("Time Units (Clock)", fontsize=11, fontweight='bold')
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"[INFO] Gantt chart timeline saved: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="UNIX Process Scheduling Simulation: Round Robin & MLFQ (Time Slice = 3 units)"
    )
    parser.add_argument("--processes", "-n", type=int, default=12, help="Number of random processes (default: 12)")
    parser.add_argument("--time-slice", "-q", type=int, default=3, help="Round robin time slice/quantum (default: 3 units)")
    parser.add_argument("--sim-time", "-t", type=int, default=60, help="Fixed simulation duration (default: 60 units)")
    parser.add_argument("--fixed-burst", "-b", type=int, default=6, help="Burst time for fixed burst mode (default: 6 units)")
    parser.add_argument("--min-burst", type=int, default=2, help="Min burst time for variable burst (default: 2)")
    parser.add_argument("--max-burst", type=int, default=12, help="Max burst time for variable burst (default: 12)")
    parser.add_argument("--seed", "-s", type=int, default=42, help="Random seed for reproducible results (default: 42)")
    
    args = parser.parse_args()
    
    print_banner("UNIX OPERATING SYSTEM PROCESS SCHEDULING SIMULATION")
    print("Project: Round Robin Time Slicing with Multilevel Feedback")
    print(f"Parameters: Time Slice = {args.time_slice} units | Fixed Sim Time = {args.sim_time} units | Processes = {args.processes}")
    
    # 1. Generate Processes with Fixed Burst Time (Random Arrivals)
    fixed_workload = generate_processes(
        num_processes=args.processes,
        burst_mode="fixed",
        fixed_burst=args.fixed_burst,
        max_arrival_time=int(args.sim_time * 0.45),
        seed=args.seed
    )
    
    # 2. Generate Processes with Variable (Randomized) Burst Time (Random Arrivals)
    var_workload = generate_processes(
        num_processes=args.processes,
        burst_mode="variable",
        min_burst=args.min_burst,
        max_burst=args.max_burst,
        max_arrival_time=int(args.sim_time * 0.45),
        seed=args.seed + 10  # Different seed for variable bursts
    )
    
    # Schedulers
    rr = RoundRobinScheduler(time_slice=args.time_slice, max_time=args.sim_time)
    mlfq = UnixMLFQScheduler(base_time_slice=args.time_slice, num_queues=3, max_time=args.sim_time)
    
    # Run simulations
    print_section("RUN 1: Standard Round Robin (Fixed Burst Times)")
    res_rr_fixed = rr.run(fixed_workload, burst_mode="Fixed")
    print_process_table(res_rr_fixed)
    print_ascii_gantt(res_rr_fixed)
    print_metrics_summary(res_rr_fixed)
    
    print_section("RUN 2: Standard Round Robin (Variable / Randomized Burst Times)")
    res_rr_var = rr.run(var_workload, burst_mode="Variable")
    print_process_table(res_rr_var)
    print_ascii_gantt(res_rr_var)
    print_metrics_summary(res_rr_var)
    
    print_section("RUN 3: UNIX Multilevel Feedback Queue (Fixed Burst Times)")
    res_mlfq_fixed = mlfq.run(fixed_workload, burst_mode="Fixed")
    print_process_table(res_mlfq_fixed)
    print_ascii_gantt(res_mlfq_fixed)
    print_metrics_summary(res_mlfq_fixed)
    
    print_section("RUN 4: UNIX Multilevel Feedback Queue (Variable / Randomized Burst Times)")
    res_mlfq_var = mlfq.run(var_workload, burst_mode="Variable")
    print_process_table(res_mlfq_var)
    print_ascii_gantt(res_mlfq_var)
    print_metrics_summary(res_mlfq_var)
    
    # Comparative Summary Table
    print_section("FINAL COMPARATIVE ANALYSIS (Fixed vs. Variable Burst Times)")
    summary_headers = [
        "Algorithm", "Burst Mode", "Completed", "Incomplete", "Avg Waiting Time", "Avg Turnaround", "CPU Util", "Throughput"
    ]
    all_results = [res_rr_fixed, res_rr_var, res_mlfq_fixed, res_mlfq_var]
    summary_rows = []
    for r in all_results:
        summary_rows.append([
            r.algorithm_name,
            r.burst_mode,
            f"{len(r.completed_processes)}/{len(r.all_processes)}",
            f"{len(r.incomplete_processes)}",
            f"{r.avg_waiting_time:.2f} units",
            f"{r.avg_turnaround_time:.2f} units",
            f"{r.cpu_utilization:.1f}%",
            f"{r.throughput:.4f}/t"
        ])
    print(format_table(summary_headers, summary_rows))
    
    # Export artifacts
    export_csv_summary(all_results, "simulation_summary.csv")
    plot_comparison_graphs(all_results, "comparison_metrics.png")
    plot_gantt_chart(all_results, "gantt_chart.png")
    
    print_banner("SIMULATION COMPLETED SUCCESSFULLY")


if __name__ == "__main__":
    main()
