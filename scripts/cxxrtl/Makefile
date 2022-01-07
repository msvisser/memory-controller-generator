sim: sim.cpp test.o
	clang++ -O3 -std=c++14 -Wall -Wextra -I /usr/share/yosys/include $^ -o $@

test.o: test.cpp
	clang++ -O3 -std=c++14 -Wall -Wextra -I /usr/share/yosys/include -c $^ -o $@

test.cpp: test.il
	yosys -p 'delete $$verilog_initial_trigger; write_cxxrtl -header $@' $^

test.il:
	python -m memory_controller_generator.testbench.cxxrtl -c HsiaoCode generate $@

run: sim
	./sim 1000000 0.0001
clean:
	rm -f sim test.il test.o test.cpp test.h
.PHONY: clean run
