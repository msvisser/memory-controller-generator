# User config
set ::env(DESIGN_NAME) top

# Change if needed
set ::env(VERILOG_FILES) [glob $::env(DESIGN_DIR)/src/*.v]

# Fill this
set ::env(CLOCK_PERIOD) "2.0"
set ::env(CLOCK_PORT) "clk"

# Ignore delays for input and output pins
set ::env(IO_PCT) "0"

set ::env(PL_TARGET_DENSITY) "0.45"
set ::env(FP_CORE_UTIL) "30"

set ::env(GLB_RT_ADJUSTMENT) 0.05

set ::env(DESIGN_IS_CORE) "0"
set ::env(DIODE_INSERTION_STRATEGY) "3"
set ::env(SYNTH_STRATEGY) "DELAY 0"
set ::env(SYNTH_SIZING) "1"

set filename $::env(DESIGN_DIR)/$::env(PDK)_$::env(STD_CELL_LIBRARY)_config.tcl
if { [file exists $filename] == 1} {
	source $filename
}

