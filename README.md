# memory-controller-generator
`memory-controller-generator` is a Python package for generating error correcting memory controller hardware designs. The hardware is built using the [Amaranth](https://github.com/amaranth-lang/amaranth) (formerly nMigen) hardware design language. Currently, there are eight error correction codes and three memory controller designs implemented. However, this project is designed to allow for easy addition of error correction codes and memory controller implementations.

The following error correction codes are supported:
- Identity (no error correction or detection)
- Parity (SED)
- Hamming (SEC) and extended Hamming (SEC-DED) [^1]
- Hsiao (SEC-DED), two implementation variants available [^2] [^3]
- Dutta and Touba (SEC-DAEC-DED) [^4]
- She and Li (SEC-DAEC-DAAEC-TAEC) [^5]

[^1]: Hamming, R. W. (1950). Error Detecting and Error Correcting Codes. _The Bell Systems Technical Journal, 29(2)_, 147–160. https://doi.org/10.1002/j.1538-7305.1950.tb00463.x
[^2]: Hsiao, M. Y. (1970). A Class of Optimal Minimum Odd-weight-column SEC-DED Codes. _IBM Journal of Research & Development_, 395–401.
[^3]: Chen, L. (2008). _Hsiao-Code Check Matrices and Recursively Balanced Matrices_. https://arxiv.org/abs/0803.1217
[^4]: Dutta, A. and Touba, N. A. (2007). Multiple Bit Upset Tolerant Memory Using a Selective Cycle Avoidance Based SEC-DED-DAEC Code. _25th IEEE VLSI Test Symposium (VTS’07)_, 349–354. https://doi.org/10.1109/VTS.2007.40
[^5]: She, X., Li, N. and Waileen Jensen, D. (2012). SEU tolerant memory using error correction code. _IEEE Transactions on Nuclear Science 59 (1 PART 2)_, 205–210. https://doi.org/10.1109/TNS.2011.2176513

Furthermore, the following memory controllers are supported:
- Basic, only correct read responses without touching the memory.
- Write-back, automatically overwrite errors in memory when read.
- Refresh, periodically refresh every memory location.

## Requirements
All the Python requirements for this package can be automatically installed from PyPi. However, the testing [scripts](scripts) do require some additional tools, and some packages, which are specified in [`requirements.txt`](requirements.txt).

The following tools are required for simulation:
- [Yosys](https://github.com/YosysHQ/yosys) 0.12+45

The following tools are required for formal verification:
- [SymbiYosys](https://github.com/YosysHQ/sby)
- [Boolector](https://github.com/Boolector/boolector) 3.2

The following tools are required for synthesis and tape-out:
- [OpenLane](https://github.com/The-OpenROAD-Project/OpenLane)

## Architecture
This package is designed to consist of two parts. First, there is the error correction submodule, which contains the implementations of all error correction codes. Second, there is the memory controller submodule, which contians the implementations of the memory controllers. Both are designed for easy addition of new error correction codes or memory controller designs.

#### Error correction
The error correction submodule defines a base class `GenericCode`, which can be used by implementations of error correction codes to simplify the implementation. `GenericCode` is designed to be flexible in the number of data and parity bits that are used by the error correction code. Most actual implementations of error correction codes will only allow the user to set the number of data bits and will infer the number of parity bits.

Implementations of `GenericCode` are required to implement `generate_matrices()`, which is called when the code is expected to generate the parity-check and generator matrices. Furthermore, the error correction code is also required to generate a list of correctable and detectable errors.

All the actual hardware implementation of an error correction code can be inherited from `GenericCode`. It provides a `GenericEncoder` and `GenericDecoder`, which can be used with any valid pair of parity-check and generator matrix. The `GenericDecoder` is build up of two other parts, the `GenericFlipCalculator` and `GenericErrorCalculator`.

The decoder will always calculate the syndrome based on the parity-check matrix and the input bits. This syndrome is then forwarded to the flip calculator to determine which bits in the output have to be flipped for the output to become correct. Finally, the calculated syndrome and flips are forwarded to the error calculator, which determines whether an error has occurred and whether it was correctable.

An error correction implementation can choose to override any of the provided generic hardware modules if it wants to. Because most error correction implementations only want to override a small part of the decoder, the extra submodules were introduced. This allows a code to only override the error or flip calculator, while keeping the rest of the generic decoder. This feature is used by the `ExtendedHammingCode` and `HsiaoCode` to simplify detecting uncorrectable errors.

Finally, there is a second base class, `BoolectorCode`, which can be used by implementations of error correction codes. `BoolectorCode` provides an easy way of generating the parity-check matrix for an error correction code, where defining specific conditions on the parity-check matrix is simple, however finding an actual matrix satisfying those conditions is non-trivial.

`BoolectorCode` uses the Boolector SAT framework to allow defining error correction codes using boolean equations on the parity-check matrix. Boolector will automatically find a parity-check matrix which satisfies the supplied conditions, or will fail if such a matrix does not exist. Furthermore, `BoolectorCode` can also optimize the parity-check matrix based on some optimization goals. This optimization is done by incrementally restricting allowable matrices based on the optimization goals. Both the `DuttaToubaCode` and `SheLiCode` implementation use this feature to generate their parity-check matrices.

#### Memory controller
The memory controller submodule also defines a base class `GenericController`, however in this case more work is required to build a memory controller. `GenericController` only defines the input and output wires to the controller, but any of the actual logic has to be defined in the controller implementation.

Memory controller designs have three bundles of signals to deal with, there is the user request and response interface, and the SRAM interface. The user request and response interfaces are both simple ready-valid interfaces. The SRAM interface is a simple single-port SRAM interface with a clock, clock enable, write enable, address, and read and write data.

Each memory controller implementation should instantiate an encoder and decoder of the error correction code supplied. After this most of the signals can be directly connected between the modules and interfaces. In the simples memory controller design only some simple logic and a single register is needed, next to the encoder and decoder. The `BasicController` implementation can be used as an example of such a simple controller. More complex controllers can add additional logic and state to change the behaviour. An example of a more complex controller is the `WriteBackController`.

#### Wrappers
Next to the actual memory controller implementation, there are also two memory controller wrappers implemented. These wrappers are not memory controllers themselves, but instead translate the inputs to the memory controller to add additional functionality.

The first wrapper is the `PartialWriteWrapper`. This wrapper adds the ability to handle partial write operations to a memory controller. To do this, a partial write operation will be translated into a read-modify-write cycle. Most systems using these memory controllers will likely need this feature, so they can add this wrapper in front of the memory controller.

The second wrapper is the `RefreshWrapper`. This wrapper provides automatic refresh support through a wrapper, instead of implementing it directly in the controller. The refresh wrapper will periodically issue a read request to the memory controller and then discard the response. For this to actually have any effect it has to be combined with a memory controller that repairs errors automatically, such as the `WriteBackController`. Since this combination is likely to be used as a memory controller, the package provides a `RefreshController` which already bundles both modules.
