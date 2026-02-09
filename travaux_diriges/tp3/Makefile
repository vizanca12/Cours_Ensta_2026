# Define o shell como bash para garantir que o comando 'source' funcione
SHELL := /bin/bash

# O alvo principal. O '@' no início esconde o comando longo do terminal.
run:
	@source venv/bin/activate && \
	mpirun -n 20 python bucket_sort.py && \
	deactivate
	

