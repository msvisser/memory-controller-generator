sim: sim.cpp test.o test.h
	clang++ -O3 -std=c++14 -Wall -Wextra -I /usr/share/yosys/include sim.cpp test.o -o sim

test.o: test.cpp
	clang++ -O3 -std=c++14 -Wall -Wextra -I /usr/share/yosys/include -c test.cpp -o test.o

test.cpp: ../test.v
	yosys -p 'write_cxxrtl -header test.cpp' ../test.v

run: sim
	./sim 1000000 0.0001
clean:
	rm -f sim test.o test.cpp test.h
.PHONY: clean run
