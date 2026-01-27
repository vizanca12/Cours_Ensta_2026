#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <time.h>
#include <mpi.h>

void generate_random_coordinates(double *x, double *y) {
    *x = (double)rand() / RAND_MAX * 2.0 - 1.0;
    *y = (double)rand() / RAND_MAX * 2.0 - 1.0;
}

int main(int argc, char** argv) {
    MPI_Init(&argc, &argv);

    int rank, nbp;
    // all the process execute the same code
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &nbp);

    double start_time = MPI_Wtime();
    // starts the process with the random seed
    srand(time(NULL) + rank * 100); 

    long long total_points = 1000000; 
    // each process gets a portion of the whole calculus
    long long points_per_process = total_points / nbp; 

    long long local_inside = 0;
    double x, y;

    for (long long i = 0; i < points_per_process; i++) {
        generate_random_coordinates(&x, &y);
        if ((x*x + y*y) <= 1.0) {
            local_inside++;
        }
    }

    long long global_inside = 0;
    // collects ("reduce") each value to a single buffer in the "global_inside" points
    MPI_Reduce(&local_inside, &global_inside, 1 /* number of elements to "reduce" */, MPI_LONG_LONG, MPI_SUM, 0, MPI_COMM_WORLD);

    double end_time = MPI_Wtime();

    if (rank == 0) {
        double pi = 4.0 * (double)global_inside / (double)(points_per_process * nbp);
        printf("Pi with %lld points: %f\n\nTime: %f\n", points_per_process * nbp, pi, end_time - start_time);
    }

    MPI_Finalize();
    return 0;
}