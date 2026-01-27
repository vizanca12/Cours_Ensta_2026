#include <stdio.h>
#include <mpi.h>


// mpicc 2_1.c -Wall -pedantic -O2 -o 2_1.exe 

// Message Passing Interface = MPI
// MPI is different from "fork()" because it creates the process before the program runs (mpirun) = no "parent" process
int main(int argc, char** argv) {
    MPI_Init(&argc, &argv); // init all the "process"

    int rank, nbp; // nbp = number os processes, it comes as argv
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &nbp);

    int token;
    int tag = 0;

    if (rank == 0) {
        // first step: init + send
        token = 1;
        // send the token to the "id 1"
        MPI_Send(&token, 1, MPI_INT, 1, tag, MPI_COMM_WORLD);
        printf("Rank 0 : send %d for 1\n", token);

        // seventh step, rank zero receives the last number
        MPI_Recv(&token, 1, MPI_INT, nbp - 1, tag, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
        printf("Rank 0 : received the last %d from rank %d\n", token, nbp - 1);

    } else {
        // steps 2 to 6, the other ranks wait the message from the last rank
        MPI_Recv(&token, 1, MPI_INT, rank - 1, tag, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
        
        // the token is incremented
        token += 1;

        // send the changed token to the next rank
        int dest = (rank + 1) % nbp; 
        MPI_Send(&token, 1, MPI_INT, dest, tag, MPI_COMM_WORLD);
    }

    MPI_Finalize();
    return 0;
}