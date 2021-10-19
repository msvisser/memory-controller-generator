#include <stdio.h>
#include <stdint.h>
#include <fstream>
#include <math.h>
#include <random>
#include <bit>
#include <backends/cxxrtl/cxxrtl_vcd.h>
#include "test.h"

static cxxrtl_design::p_top top;
#ifdef VCD
static cxxrtl::vcd_writer vcd;
static size_t steps = 0;
#endif

static size_t num_memory_cells = top.memory_p_mem.depth();
static size_t num_memory_bits = top.memory_p_mem.data[0].bits;

// Flip the clock high and low
void clk() {
    top.p_clk.set<bool>(true);
    top.step();
#ifdef VCD
    vcd.sample(steps);
    steps += 5;
#endif

    top.p_clk.set<bool>(false);
    top.step();
#ifdef VCD
    vcd.sample(steps);
    steps += 5;
#endif
}

int main(int argc, char *argv[]) {
    // Two arguments are required for number of cycles and error rate
    if (argc < 3) {
        return 1;
    }

#ifdef VCD
    // debug_items maps the hierarchical names of signals and memories in the design
    // to a cxxrtl_object (a value, a wire, or a memory)
    cxxrtl::debug_items all_debug_items;

    // Load the debug items of the top down the whole design hierarchy
    top.debug_info(all_debug_items);

    // vcd_writer is the CXXRTL object that's responsible of creating a string with
    // the VCD file contents.
    vcd.timescale(1, "ns");

    // Here we tell the vcd writer to dump all the signals of the design, except for the
    // memories, to the VCD file.
    //
    // It's not necessary to load all debug objects to the VCD. There is, for example,
    // a  vcd.add(<debug items>, <filter>)) method which allows creating your custom filter to decide
    // what to add and what not.
    // vcd.add_without_memories(all_debug_items);
    vcd.add(all_debug_items);

    std::ofstream waves("waves.vcd");
#endif

    // Get the arguments
    size_t total_cycles = std::strtoull(argv[1], NULL, 10);
    double lambda = std::strtod(argv[2], NULL);

    // Setup random numbers
    size_t seed = time(NULL);
    std::mt19937_64 generator(seed);
    std::poisson_distribution<size_t> num_flips(lambda);
    std::uniform_int_distribution<size_t> memory_cell(0, num_memory_cells - 1);
    std::uniform_int_distribution<size_t> memory_bit(0, num_memory_bits - 1);

    // Keep track of flips
    size_t flips_array[num_memory_cells];
    for (size_t i = 0; i < num_memory_cells; ++i) {
        flips_array[i] = 0;
    }

    auto dump_mem = [&flips_array]{
        printf("      memory       flip        real   \n");
        for (size_t i = 0; i < num_memory_cells; ++i) {
            size_t mem_val = top.memory_p_mem[i].get<size_t>();
            size_t flip_val = flips_array[i];
            printf("%02zx: %010zx  %010zx  %010zx\n", i, mem_val, flip_val, mem_val ^ flip_val);
        }
    };

    top.p_clk.set<bool>(false);
    top.step();
#ifdef VCD
    vcd.sample(0);
#endif

    size_t req_valid_cycles = 0;
    size_t req_fire_cycles = 0;
    size_t rsp_ready_cycles = 0;
    size_t rsp_fire_cycles = 0;
    size_t errors_injected = 0;
    size_t read_with_errors[num_memory_bits + 1];
    for (size_t i = 0; i < num_memory_bits + 1; ++i) {
        read_with_errors[i] = 0;
    }


    for (size_t clk_cycle = 0; clk_cycle < total_cycles; ++clk_cycle) {
        // Flip memory bit(s) if randomly required to do so
        size_t flips = num_flips(generator);
        while(flips--) {
            size_t cell = memory_cell(generator);
            size_t bit = memory_bit(generator);

            flips_array[cell] ^= (1ull << bit);

            bool was = top.memory_p_mem.data[cell].bit(bit);
            top.memory_p_mem.data[cell].set_bit(bit, !was);

            // printf("flipped %lu:%lu from %d to %d\n", cell, bit, was, !was);
            errors_injected++;
        }

        // Print the requests and responses
        if (top.p_rsp____ready.get<bool>()) {
            rsp_ready_cycles++;
        }
        if (top.p_rsp____valid.get<bool>() && top.p_rsp____ready.get<bool>()) {
            rsp_fire_cycles++;
            // printf("%03zd >> rsp  data: %d  error: %d  uncorrectable: %d\n", clk_cycle, top.p_rsp____read__data.get<uint32_t>(), top.p_rsp____error.get<bool>(), top.p_rsp____uncorrectable__error.get<bool>());
            // if (top.p_rsp____uncorrectable__error.get<bool>()) {
            //     break;
            // }
        }
        if (top.p_req____valid.get<bool>()) {
            req_valid_cycles++;
            if (top.p_req____ready.get<bool>()) {
                req_fire_cycles++;
                // printf("%03zd >> req  addr: %zx  write: %d  data: %x\n", clk_cycle, top.p_req____addr.get<size_t>(), top.p_req____write__en.get<bool>(), top.p_req____write__data.get<uint32_t>());
            }
        }

        bool sram_clk_en = top.p_sram____clk__en.get<bool>();
        bool sram_write_en = top.p_sram____write__en.get<bool>();
        size_t sram_addr = top.p_sram____addr.get<size_t>();

        // Reset the flips array
        if (sram_clk_en && !sram_write_en) {
            // printf("read from %zx\n", sram_addr);
            auto popcnt = std::__popcount(flips_array[sram_addr]);
            read_with_errors[popcnt]++;
            if (popcnt == 1) {
                // printf("expecting error!\n");
                // dump_mem();
            } else if (popcnt > 1) {
                // printf("uncorrectable error!\n");
                // break;
            }
        }
        if (sram_clk_en && sram_write_en) {
            // printf("write to %zx <- %010zx\n", sram_addr, top.p_sram____write__data.get<size_t>());
            flips_array[sram_addr] = 0;
        }

        // printf("\n");

        clk();

        if (sram_clk_en && sram_write_en) {
            // printf("is now: %010zx\n", top.memory_p_mem.data[sram_addr].get<size_t>());
        }
    }

    top.p_clk.set<bool>(false);
    top.step();
#ifdef VCD
    vcd.sample(steps);
    steps += 5;
#endif

    // dump_mem();

    printf("req_valid_cycles: %zd\n", req_valid_cycles);
    printf("req_fire_cycles: %zd\n", req_fire_cycles);
    printf("rsp_ready_cycles: %zd\n", rsp_ready_cycles);
    printf("rsp_fire_cycles: %zd\n", rsp_fire_cycles);

    printf("errors_injected: %zd\n", errors_injected);
    for (size_t i = 0; i < 5; ++i) {
        printf("read_with_errors[%zd] = %zd\n", i, read_with_errors[i]);
    }

#ifdef VCD
    waves << vcd.buffer;
    vcd.buffer.clear();
#endif
}
