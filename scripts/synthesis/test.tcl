yosys -import

set lib_file /home/michiel/tue/Thesis/OpenLane/pdks/skywater-pdk/libraries/sky130_fd_sc_hd/latest/timing/sky130_fd_sc_hd__tt_025C_1v80.lib
read_liberty -lib ${lib_file}

prep -flatten -top top

synth
abc -g all
abc -liberty ${lib_file} -constr test.sdc -D 5000
opt_clean -purge

# tee -a /dev/stdout stat -liberty ${lib_file}
stat -liberty ${lib_file}
