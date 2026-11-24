/*
 * ==============================================================================
 * UNIX Process Scheduling Simulator: Round Robin with Multilevel Feedback (MLFQ)
 * Language: C (C99 Standard)
 *
 * Simulates Round Robin time slicing (Quantum = 3 units) and UNIX Multilevel
 * Feedback Queue (MLFQ) with fixed and variable (randomized) burst times.
 * Runs processes for a fixed total simulation time and calculates Average Waiting
 * Time (AWT) and Average Turnaround Time (TAT) for completed processes.
 * ==============================================================================
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <time.h>

#define MAX_PROCESSES 64
#define MAX_GANTT_SLICES 256
#define NUM_QUEUES 3
#define BASE_TIME_SLICE 3

typedef enum {
    STATE_NEW,
    STATE_READY,
    STATE_RUNNING,
    STATE_TERMINATED,
    STATE_INCOMPLETE
} ProcessState;

/* Process Control Block (PCB) */
typedef struct {
    int pid;
    char name[16];
    int arrival_time;
    int burst_time;
    int remaining_time;
    int priority;
    int current_queue;
    ProcessState state;
    
    int start_time;         /* -1 if not started */
    int completion_time;    /* -1 if incomplete */
    int waiting_time;
    int turnaround_time;
    int response_time;
    int cpu_cycles_used;
} PCB;

typedef struct {
    int pid;
    char name[16];
    int start_time;
    int end_time;
    bool is_idle;
} GanttSlice;

typedef struct {
    char algorithm_name[64];
    char burst_mode[32];
    int time_slice;
    int max_simulation_time;
    int total_processes;
    int completed_count;
    int incomplete_count;
    
    double avg_waiting_time;
    double avg_turnaround_time;
    double avg_response_time;
    double cpu_utilization;
    double throughput;
    
    int busy_time;
    int idle_time;
    
    GanttSlice gantt[MAX_GANTT_SLICES];
    int gantt_count;
    
    PCB processes[MAX_PROCESSES];
} SimulationResult;

/* Simple Queue Implementation */
typedef struct {
    int items[MAX_PROCESSES];
    int front;
    int rear;
    int size;
} Queue;

void init_queue(Queue *q) {
    q->front = 0;
    q->rear = -1;
    q->size = 0;
}

bool is_empty(Queue *q) {
    return q->size == 0;
}

void enqueue(Queue *q, int pcb_idx) {
    if (q->size < MAX_PROCESSES) {
        q->rear = (q->rear + 1) % MAX_PROCESSES;
        q->items[q->rear] = pcb_idx;
        q->size++;
    }
}

int dequeue(Queue *q) {
    if (is_empty(q)) return -1;
    int item = q->items[q->front];
    q->front = (q->front + 1) % MAX_PROCESSES;
    q->size--;
    return item;
}

/* Helper to compare arrival times for sorting */
int compare_arrivals(const void *a, const void *b) {
    const PCB *p1 = (const PCB *)a;
    const PCB *p2 = (const PCB *)b;
    if (p1->arrival_time != p2->arrival_time) {
        return p1->arrival_time - p2->arrival_time;
    }
    return p1->pid - p2->pid;
}

/* Generate random arrival workload */
void generate_workload(PCB procs[], int n, const char *burst_mode, int fixed_burst, int min_burst, int max_burst, int max_arrival, unsigned int seed) {
    srand(seed);
    for (int i = 0; i < n; i++) {
        procs[i].pid = i + 1;
        snprintf(procs[i].name, sizeof(procs[i].name), "P%d", i + 1);
        procs[i].arrival_time = rand() % (max_arrival + 1);
        
        if (strcmp(burst_mode, "Fixed") == 0) {
            procs[i].burst_time = fixed_burst;
        } else {
            procs[i].burst_time = min_burst + (rand() % (max_burst - min_burst + 1));
        }
        
        procs[i].remaining_time = procs[i].burst_time;
        procs[i].priority = 0;
        procs[i].current_queue = 0;
        procs[i].state = STATE_NEW;
        procs[i].start_time = -1;
        procs[i].completion_time = -1;
        procs[i].waiting_time = 0;
        procs[i].turnaround_time = 0;
        procs[i].response_time = -1;
        procs[i].cpu_cycles_used = 0;
    }
    
    /* Sort by arrival time */
    qsort(procs, n, sizeof(PCB), compare_arrivals);
    /* Re-index PIDs in order of arrival for clarity */
    for (int i = 0; i < n; i++) {
        procs[i].pid = i + 1;
        snprintf(procs[i].name, sizeof(procs[i].name), "P%d", i + 1);
    }
}

/* Clone workload array */
void clone_workload(const PCB src[], PCB dst[], int n) {
    for (int i = 0; i < n; i++) {
        dst[i] = src[i];
        dst[i].remaining_time = src[i].burst_time;
        dst[i].state = STATE_NEW;
        dst[i].start_time = -1;
        dst[i].completion_time = -1;
        dst[i].waiting_time = 0;
        dst[i].turnaround_time = 0;
        dst[i].response_time = -1;
        dst[i].cpu_cycles_used = 0;
    }
}

/* Add slice to Gantt */
void add_gantt(SimulationResult *res, int pid, const char *name, int start, int end, bool is_idle) {
    if (res->gantt_count < MAX_GANTT_SLICES) {
        GanttSlice *s = &res->gantt[res->gantt_count++];
        s->pid = pid;
        strncpy(s->name, name, sizeof(s->name) - 1);
        s->start_time = start;
        s->end_time = end;
        s->is_idle = is_idle;
    }
}

/* ==============================================================================
 * 1. Standard Round Robin Scheduler (Quantum = 3)
 * ============================================================================== */
void simulate_round_robin(const PCB input_procs[], int n, int time_slice, int max_time, const char *burst_mode, SimulationResult *res) {
    memset(res, 0, sizeof(SimulationResult));
    strncpy(res->algorithm_name, "Round Robin (RR)", sizeof(res->algorithm_name) - 1);
    strncpy(res->burst_mode, burst_mode, sizeof(res->burst_mode) - 1);
    res->time_slice = time_slice;
    res->max_simulation_time = max_time;
    res->total_processes = n;
    
    clone_workload(input_procs, res->processes, n);
    
    Queue ready_q;
    init_queue(&ready_q);
    
    int current_time = 0;
    int next_arrival_idx = 0;
    int total_busy = 0;
    int total_idle = 0;
    
    while (current_time < max_time) {
        /* Admit new arrivals */
        while (next_arrival_idx < n && res->processes[next_arrival_idx].arrival_time <= current_time) {
            res->processes[next_arrival_idx].state = STATE_READY;
            enqueue(&ready_q, next_arrival_idx);
            next_arrival_idx++;
        }
        
        if (is_empty(&ready_q)) {
            /* CPU Idle */
            if (next_arrival_idx < n) {
                int next_arr = res->processes[next_arrival_idx].arrival_time;
                int idle_len = (next_arr - current_time < max_time - current_time) ? 
                               (next_arr - current_time) : (max_time - current_time);
                if (idle_len > 0) {
                    add_gantt(res, -1, "IDLE", current_time, current_time + idle_len, true);
                    current_time += idle_len;
                    total_idle += idle_len;
                }
                continue;
            } else {
                int rem_sim = max_time - current_time;
                if (rem_sim > 0) {
                    add_gantt(res, -1, "IDLE", current_time, max_time, true);
                    total_idle += rem_sim;
                    current_time = max_time;
                }
                break;
            }
        }
        
        int p_idx = dequeue(&ready_q);
        PCB *p = &res->processes[p_idx];
        p->state = STATE_RUNNING;
        
        if (p->start_time == -1) {
            p->start_time = current_time;
            p->response_time = current_time - p->arrival_time;
        }
        
        int max_exec = max_time - current_time;
        int exec_time = p->remaining_time;
        if (exec_time > time_slice) exec_time = time_slice;
        if (exec_time > max_exec) exec_time = max_exec;
        
        int slice_start = current_time;
        int slice_end = current_time + exec_time;
        add_gantt(res, p->pid, p->name, slice_start, slice_end, false);
        
        p->remaining_time -= exec_time;
        p->cpu_cycles_used += exec_time;
        current_time = slice_end;
        total_busy += exec_time;
        
        /* Admit processes that arrived while running this slice */
        while (next_arrival_idx < n && res->processes[next_arrival_idx].arrival_time <= current_time) {
            res->processes[next_arrival_idx].state = STATE_READY;
            enqueue(&ready_q, next_arrival_idx);
            next_arrival_idx++;
        }
        
        if (p->remaining_time == 0) {
            p->completion_time = current_time;
            p->turnaround_time = p->completion_time - p->arrival_time;
            p->waiting_time = p->turnaround_time - p->burst_time;
            p->state = STATE_TERMINATED;
        } else {
            if (current_time >= max_time) {
                p->state = STATE_INCOMPLETE;
            } else {
                p->state = STATE_READY;
                enqueue(&ready_q, p_idx);
            }
        }
    }
    
    /* Calculate Statistics for Completed Processes */
    int completed = 0;
    int incomplete = 0;
    double sum_wt = 0;
    double sum_tat = 0;
    double sum_rt = 0;
    int started_count = 0;
    
    for (int i = 0; i < n; i++) {
        PCB *p = &res->processes[i];
        if (p->remaining_time == 0 && p->completion_time != -1 && p->completion_time <= max_time) {
            p->state = STATE_TERMINATED;
            completed++;
            sum_wt += p->waiting_time;
            sum_tat += p->turnaround_time;
        } else {
            p->state = STATE_INCOMPLETE;
            incomplete++;
            if (p->start_time != -1) {
                p->waiting_time = (max_time - p->arrival_time) - (p->burst_time - p->remaining_time);
            } else {
                p->waiting_time = (max_time > p->arrival_time) ? (max_time - p->arrival_time) : 0;
            }
        }
        if (p->start_time != -1) {
            sum_rt += p->response_time;
            started_count++;
        }
    }
    
    res->completed_count = completed;
    res->incomplete_count = incomplete;
    res->busy_time = total_busy;
    res->idle_time = total_idle;
    res->avg_waiting_time = (completed > 0) ? (sum_wt / completed) : 0.0;
    res->avg_turnaround_time = (completed > 0) ? (sum_tat / completed) : 0.0;
    res->avg_response_time = (started_count > 0) ? (sum_rt / started_count) : 0.0;
    int total_sim_elapsed = total_busy + total_idle;
    res->cpu_utilization = (total_sim_elapsed > 0) ? ((double)total_busy / total_sim_elapsed * 100.0) : 0.0;
    res->throughput = (total_sim_elapsed > 0) ? ((double)completed / total_sim_elapsed) : 0.0;
}

/* ==============================================================================
 * 2. UNIX Multilevel Feedback Queue (MLFQ) Simulator
 * ============================================================================== */
void simulate_unix_mlfq(const PCB input_procs[], int n, int base_time_slice, int max_time, const char *burst_mode, SimulationResult *res) {
    memset(res, 0, sizeof(SimulationResult));
    strncpy(res->algorithm_name, "UNIX Multilevel Feedback Queue (MLFQ)", sizeof(res->algorithm_name) - 1);
    strncpy(res->burst_mode, burst_mode, sizeof(res->burst_mode) - 1);
    res->time_slice = base_time_slice;
    res->max_simulation_time = max_time;
    res->total_processes = n;
    
    clone_workload(input_procs, res->processes, n);
    
    Queue mlfq_queues[NUM_QUEUES];
    int quantums[NUM_QUEUES];
    for (int q = 0; q < NUM_QUEUES; q++) {
        init_queue(&mlfq_queues[q]);
        quantums[q] = base_time_slice * (1 << q); /* Q0: 3, Q1: 6, Q2: 12 */
    }
    
    int current_time = 0;
    int next_arrival_idx = 0;
    int total_busy = 0;
    int total_idle = 0;
    int aging_interval = 24;
    int last_aging_time = 0;
    
    while (current_time < max_time) {
        /* Admit new arrivals into Queue 0 (highest priority) */
        while (next_arrival_idx < n && res->processes[next_arrival_idx].arrival_time <= current_time) {
            res->processes[next_arrival_idx].state = STATE_READY;
            res->processes[next_arrival_idx].current_queue = 0;
            enqueue(&mlfq_queues[0], next_arrival_idx);
            next_arrival_idx++;
        }
        
        /* Priority aging mechanism */
        if (aging_interval > 0 && (current_time - last_aging_time) >= aging_interval) {
            for (int q = 1; q < NUM_QUEUES; q++) {
                while (!is_empty(&mlfq_queues[q])) {
                    int b_idx = dequeue(&mlfq_queues[q]);
                    int target_q = q - 1;
                    res->processes[b_idx].current_queue = target_q;
                    enqueue(&mlfq_queues[target_q], b_idx);
                }
            }
            last_aging_time = current_time;
        }
        
        /* Find highest priority non-empty queue */
        int active_q = -1;
        for (int q = 0; q < NUM_QUEUES; q++) {
            if (!is_empty(&mlfq_queues[q])) {
                active_q = q;
                break;
            }
        }
        
        if (active_q == -1) {
            /* Idle */
            if (next_arrival_idx < n) {
                int next_arr = res->processes[next_arrival_idx].arrival_time;
                int idle_len = (next_arr - current_time < max_time - current_time) ? 
                               (next_arr - current_time) : (max_time - current_time);
                if (idle_len > 0) {
                    add_gantt(res, -1, "IDLE", current_time, current_time + idle_len, true);
                    current_time += idle_len;
                    total_idle += idle_len;
                }
                continue;
            } else {
                int rem_sim = max_time - current_time;
                if (rem_sim > 0) {
                    add_gantt(res, -1, "IDLE", current_time, max_time, true);
                    total_idle += rem_sim;
                    current_time = max_time;
                }
                break;
            }
        }
        
        int p_idx = dequeue(&mlfq_queues[active_q]);
        PCB *p = &res->processes[p_idx];
        p->state = STATE_RUNNING;
        
        if (p->start_time == -1) {
            p->start_time = current_time;
            p->response_time = current_time - p->arrival_time;
        }
        
        int q_slice = quantums[active_q];
        int max_exec = max_time - current_time;
        int exec_time = p->remaining_time;
        if (exec_time > q_slice) exec_time = q_slice;
        if (exec_time > max_exec) exec_time = max_exec;
        
        int slice_start = current_time;
        int slice_end = current_time + exec_time;
        add_gantt(res, p->pid, p->name, slice_start, slice_end, false);
        
        p->remaining_time -= exec_time;
        p->cpu_cycles_used += exec_time;
        current_time = slice_end;
        total_busy += exec_time;
        
        /* Admit processes that arrived while running */
        while (next_arrival_idx < n && res->processes[next_arrival_idx].arrival_time <= current_time) {
            res->processes[next_arrival_idx].state = STATE_READY;
            res->processes[next_arrival_idx].current_queue = 0;
            enqueue(&mlfq_queues[0], next_arrival_idx);
            next_arrival_idx++;
        }
        
        if (p->remaining_time == 0) {
            p->completion_time = current_time;
            p->turnaround_time = p->completion_time - p->arrival_time;
            p->waiting_time = p->turnaround_time - p->burst_time;
            p->state = STATE_TERMINATED;
        } else {
            if (current_time >= max_time) {
                p->state = STATE_INCOMPLETE;
            } else {
                /* Demote to lower queue */
                int next_q = (active_q + 1 < NUM_QUEUES) ? active_q + 1 : NUM_QUEUES - 1;
                p->current_queue = next_q;
                p->state = STATE_READY;
                enqueue(&mlfq_queues[next_q], p_idx);
            }
        }
    }
    
    /* Calculate Statistics */
    int completed = 0;
    int incomplete = 0;
    double sum_wt = 0;
    double sum_tat = 0;
    double sum_rt = 0;
    int started_count = 0;
    
    for (int i = 0; i < n; i++) {
        PCB *p = &res->processes[i];
        if (p->remaining_time == 0 && p->completion_time != -1 && p->completion_time <= max_time) {
            p->state = STATE_TERMINATED;
            completed++;
            sum_wt += p->waiting_time;
            sum_tat += p->turnaround_time;
        } else {
            p->state = STATE_INCOMPLETE;
            incomplete++;
            if (p->start_time != -1) {
                p->waiting_time = (max_time - p->arrival_time) - (p->burst_time - p->remaining_time);
            } else {
                p->waiting_time = (max_time > p->arrival_time) ? (max_time - p->arrival_time) : 0;
            }
        }
        if (p->start_time != -1) {
            sum_rt += p->response_time;
            started_count++;
        }
    }
    
    res->completed_count = completed;
    res->incomplete_count = incomplete;
    res->busy_time = total_busy;
    res->idle_time = total_idle;
    res->avg_waiting_time = (completed > 0) ? (sum_wt / completed) : 0.0;
    res->avg_turnaround_time = (completed > 0) ? (sum_tat / completed) : 0.0;
    res->avg_response_time = (started_count > 0) ? (sum_rt / started_count) : 0.0;
    int total_sim_elapsed = total_busy + total_idle;
    res->cpu_utilization = (total_sim_elapsed > 0) ? ((double)total_busy / total_sim_elapsed * 100.0) : 0.0;
    res->throughput = (total_sim_elapsed > 0) ? ((double)completed / total_sim_elapsed) : 0.0;
}

/* ==============================================================================
 * Presentation & Output Formatting
 * ============================================================================== */
void print_separator(char ch, int len) {
    for (int i = 0; i < len; i++) putchar(ch);
    putchar('\n');
}

void print_result_table(const SimulationResult *res) {
    printf("\nProcess Execution Summary [%s - %s Burst]:\n", res->algorithm_name, res->burst_mode);
    print_separator('-', 88);
    printf("%-5s | %-7s | %-5s | %-9s | %-6s | %-10s | %-7s | %-8s | %-10s\n",
           "PID", "Arrival", "Burst", "Remaining", "Finish", "Turnaround", "Waiting", "Response", "State");
    print_separator('-', 88);
    
    for (int i = 0; i < res->total_processes; i++) {
        const PCB *p = &res->processes[i];
        char finish_str[16], tat_str[16];
        if (p->completion_time != -1) {
            snprintf(finish_str, sizeof(finish_str), "%d", p->completion_time);
            snprintf(tat_str, sizeof(tat_str), "%d", p->turnaround_time);
        } else {
            strncpy(finish_str, "-", sizeof(finish_str));
            strncpy(tat_str, "-", sizeof(tat_str));
        }
        
        const char *state_str = (p->state == STATE_TERMINATED) ? "TERMINATED" : "INCOMPLETE";
        
        printf("%-5s | %-7d | %-5d | %-9d | %-6s | %-10s | %-7d | %-8d | %-10s\n",
               p->name, p->arrival_time, p->burst_time, p->remaining_time,
               finish_str, tat_str, p->waiting_time, p->response_time, state_str);
    }
    print_separator('-', 88);
}

void print_gantt(const SimulationResult *res, int max_slices) {
    printf("\nExecution Timeline (ASCII Gantt Chart):\n");
    int count = res->gantt_count < max_slices ? res->gantt_count : max_slices;
    
    /* Top boxes */
    for (int i = 0; i < count; i++) {
        printf("[%4s]", res->gantt[i].name);
    }
    printf("\n");
    
    /* Time indicators */
    for (int i = 0; i < count; i++) {
        printf("%-6d", res->gantt[i].start_time);
    }
    if (count > 0) {
        printf("%-6d\n", res->gantt[count - 1].end_time);
    }
    if (res->gantt_count > max_slices) {
        printf("... (+%d more slices omitted for display)\n", res->gantt_count - max_slices);
    }
}

void print_metrics(const SimulationResult *res) {
    printf("\n--- Performance Metrics ---\n");
    printf("Algorithm                  : %s\n", res->algorithm_name);
    printf("Burst Mode                 : %s\n", res->burst_mode);
    printf("Time Slice                 : %d units\n", res->time_slice);
    printf("Simulation Time Limit      : %d units\n", res->max_simulation_time);
    printf("Processes Completed        : %d / %d (%.1f%%)\n",
           res->completed_count, res->total_processes,
           (double)res->completed_count / res->total_processes * 100.0);
    printf("Average Turnaround Time    : %.2f units (Completed only)\n", res->avg_turnaround_time);
    printf("Average Waiting Time       : %.2f units (Completed only)\n", res->avg_waiting_time);
    printf("Average Response Time      : %.2f units\n", res->avg_response_time);
    printf("CPU Utilization            : %.2f%% (Busy: %d, Idle: %d)\n",
           res->cpu_utilization, res->busy_time, res->idle_time);
    printf("Throughput                 : %.4f processes / unit time\n", res->throughput);
}

int main(int argc, char *argv[]) {
    int num_procs = 12;
    int time_slice = 3;
    int sim_time = 60;
    int fixed_burst = 6;
    int min_burst = 2;
    int max_burst = 12;
    unsigned int seed = 42;
    
    if (argc >= 2) num_procs = atoi(argv[1]);
    if (argc >= 3) sim_time = atoi(argv[2]);
    if (argc >= 4) time_slice = atoi(argv[3]);
    
    print_separator('=', 80);
    printf("         UNIX OPERATING SYSTEM PROCESS SCHEDULER SIMULATION (C99)\n");
    printf("  Round Robin Time Slicing (Quantum = %d) & Multilevel Feedback Queue (MLFQ)\n", time_slice);
    print_separator('=', 80);
    printf("Configuration: Processes=%d, Fixed Sim Duration=%d units, Quantum=%d units\n",
           num_procs, sim_time, time_slice);
    
    PCB fixed_procs[MAX_PROCESSES];
    PCB var_procs[MAX_PROCESSES];
    
    /* Generate Random Arrivals */
    generate_workload(fixed_procs, num_procs, "Fixed", fixed_burst, min_burst, max_burst, (int)(sim_time * 0.45), seed);
    generate_workload(var_procs, num_procs, "Variable", fixed_burst, min_burst, max_burst, (int)(sim_time * 0.45), seed + 10);
    
    SimulationResult r1, r2, r3, r4;
    
    /* 1. RR Fixed */
    printf("\n================ [ RUN 1: Round Robin - Fixed Burst Times ] ================\n");
    simulate_round_robin(fixed_procs, num_procs, time_slice, sim_time, "Fixed", &r1);
    print_result_table(&r1);
    print_gantt(&r1, 25);
    print_metrics(&r1);
    
    /* 2. RR Variable */
    printf("\n================ [ RUN 2: Round Robin - Variable Burst Times ] ================\n");
    simulate_round_robin(var_procs, num_procs, time_slice, sim_time, "Variable", &r2);
    print_result_table(&r2);
    print_gantt(&r2, 25);
    print_metrics(&r2);
    
    /* 3. MLFQ Fixed */
    printf("\n================ [ RUN 3: UNIX MLFQ - Fixed Burst Times ] ================\n");
    simulate_unix_mlfq(fixed_procs, num_procs, time_slice, sim_time, "Fixed", &r3);
    print_result_table(&r3);
    print_gantt(&r3, 25);
    print_metrics(&r3);
    
    /* 4. MLFQ Variable */
    printf("\n================ [ RUN 4: UNIX MLFQ - Variable Burst Times ] ================\n");
    simulate_unix_mlfq(var_procs, num_procs, time_slice, sim_time, "Variable", &r4);
    print_result_table(&r4);
    print_gantt(&r4, 25);
    print_metrics(&r4);
    
    /* Comparative Summary */
    printf("\n");
    print_separator('=', 88);
    printf("                     FINAL COMPARATIVE SUMMARY MATRIX\n");
    print_separator('=', 88);
    printf("%-35s | %-8s | %-9s | %-11s | %-11s | %-8s\n",
           "Algorithm", "Burst", "Completed", "Avg Waiting", "Avg TAT", "CPU Util");
    print_separator('-', 88);
    
    SimulationResult *arr[4] = {&r1, &r2, &r3, &r4};
    for (int i = 0; i < 4; i++) {
        printf("%-35s | %-8s | %d/%-7d | %-8.2f u | %-8.2f u | %-6.1f%%\n",
               arr[i]->algorithm_name,
               arr[i]->burst_mode,
               arr[i]->completed_count,
               arr[i]->total_processes,
               arr[i]->avg_waiting_time,
               arr[i]->avg_turnaround_time,
               arr[i]->cpu_utilization);
    }
    print_separator('=', 88);
    printf("\n[SUCCESS] Simulation finished successfully.\n");
    
    return 0;
}
