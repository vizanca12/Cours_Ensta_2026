1: 
	mpicc 2_1.c -Wall -pedantic -O2 -o 2_1.exe 
	mpirun -n 4 ./2_1.exe

2_mpi: 
	mpicc 2_2_mpi.c -Wall -pedantic -O2 -o 2_2.exe 
	mpirun -n 4 ./2_2.exe

2_omp: 
	mpicc -fopenmp 2_2_omp.c -Wall -pedantic -O2 -o 2_2.exe 
	./2_2.exe

3: 
	mpicc 2_3.c -Wall -pedantic -O2 -o 2_3.exe 
	mpirun -n 4 ./2_3.exe