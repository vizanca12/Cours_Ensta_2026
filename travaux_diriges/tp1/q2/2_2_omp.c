#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <omp.h> 

int main() {
    long long n_points = 100000000; // 100 million points
    long long inside = 0;

    double start_time = omp_get_wtime();

    // start
    // reduction(+:inside) : Each thread has its own copy of 'inside'.
    // at the end, OpenMP sums all copies into the global variable.
    #pragma omp parallel reduction(+:inside)
    {
        // random number management
        // use drand48_r for thread-safe random number generation.
        struct drand48_data buffer;
        srand48_r(time(NULL) + omp_get_thread_num(), &buffer);
        
        double x, y;

        // automatic distribution of the for loop among threads
        #pragma omp for
        for (long long i = 0; i < n_points; i++) {
            // thread-safe generation
            drand48_r(&buffer, &x);
            drand48_r(&buffer, &y);

            if (x * x + y * y <= 1.0) {
                inside++;
            }
        }
    }

    double end_time = omp_get_wtime();
    double pi = 4.0 * (double)inside / (double)n_points;

    printf("Pi = %f\n", pi);
    printf("Computation time : %f seconds\n", end_time - start_time);

    return 0;
}