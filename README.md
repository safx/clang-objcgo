clang-objcgo
============

clang-objcgo is a tool for generating a Go source file of wrapper interfaces for Objective-C, which can be compiled with Cgo.

## Setup

    # get clang
    cd $HOME/dev
    curl -O http://llvm.org/releases/3.4.2/clang+llvm-3.4.2-x86_64-apple-darwin10.9.xz
    tar zxf clang+llvm-3.4.2-x86_64-apple-darwin10.9.xz
    
    # get clang-python binding library
    cd clang+llvm-3.4.2-x86_64-apple-darwin10.9
    mkdir -p bindings/python/clang
    cd bindings/python/clang
    for i in __init__.py cindex.py enumerations.py ; do curl -s -O https://raw.githubusercontent.com/llvm-mirror/clang/master/bindings/python/clang/$i ; done
    cd ..
    mkdir examples && cd examples
    curl -s -O https://raw.githubusercontent.com/llvm-mirror/clang/master/bindings/python/examples/cindex/cindex-dump.py

## Usage

    # set environment variables
    export LD_LIBRARY_PATH=$($HOME/dev/clang+llvm-3.4.2-x86_64-apple-darwin10.9/bin/llvm-config --libdir)
    export PYTHONPATH=$HOME/dev/clang+llvm-3.4.2-x86_64-apple-darwin10.9/bindings/python
    
    # execute script
    git clone git@github.com:safx/clang-objcgo.git
    cd clang-objcgo
    export GOPATH=`pwd`
    python scripts/clang-objcgo.py examples/CocoaSample.h > src/sample/cocoa_sample.go

    go build main
    ./main
