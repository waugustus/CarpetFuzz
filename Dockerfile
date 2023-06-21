#
# This Dockerfile for CarpetFuzz uses Ubuntu 20.04 and
# installs LLVM 12 for afl-clang-lto support.
#

From ubuntu:20.04
COPY ./ /root/CarpetFuzz

WORKDIR /root/CarpetFuzz

# Install required dependencies
RUN apt update
RUN DEBIAN_FRONTEND=noninteractive apt install -y \
    build-essential \
    python3-dev \
    python3-pip \
    python3-setuptools \
    automake \
    cmake \
    flex \
    bison \
    libglib2.0-dev \
    libpixman-1-dev \
    cargo \
    libgtk-3-dev \
    linux-headers-$(uname -r) \
    vim \
    wget \
    curl \
    gnupg \
    autoconf \
    libtool \
    screen \
    lsb-release

# Install clang-12
RUN echo deb http://apt.llvm.org/$(lsb_release -cs)/ llvm-toolchain-$(lsb_release -cs) main >> /etc/apt/sources.list
RUN wget -O - https://apt.llvm.org/llvm-snapshot.gpg.key | apt-key add -
RUN apt-get update && apt-get upgrade -y
RUN apt install -y \
    clang-12 \
    clang-tools-12 \
    libc++1-12 \
    libc++-12-dev \
    libc++abi1-12 \
    libc++abi-12-dev \
    libclang1-12 \
    libclang-12-dev \
    libclang-common-12-dev \
    libclang-cpp12 \
    libclang-cpp12-dev \
    liblld-12 \
    liblld-12-dev \
    liblldb-12 \
    liblldb-12-dev \
    libllvm12 \
    libomp-12-dev \
    libomp5-12 \
    lld-12 \
    lldb-12 \
    llvm-12 \
    llvm-12-dev \
    llvm-12-runtime \
    llvm-12-tools
RUN update-alternatives --install /usr/bin/clang clang /usr/bin/clang-12 100 && \
    update-alternatives --install /usr/bin/clang++ clang++ /usr/bin/clang++-12 100 && \
    update-alternatives --install /usr/bin/llvm-ar llvm-ar /usr/bin/llvm-ar-12 100 && \
    update-alternatives --install /usr/bin/llvm-ranlib llvm-ranlib /usr/bin/llvm-ranlib-12 100 && \
    update-alternatives --install /usr/bin/llvm-config llvm-config /usr/bin/llvm-config-12 100 && \
    update-alternatives --install /usr/bin/llvm-link llvm-link /usr/bin/llvm-link-12 100

# Install required python modules
RUN pip3 install -r requirements.txt
RUN python3 -m spacy download en_core_web_sm-3.0.0 --direct
RUN ["python3", "-c", "import nltk; nltk.download('averaged_perceptron_tagger'); nltk.download('omw-1.4');nltk.download('punkt');nltk.download('wordnet')"]

# Download the NLP model
RUN wget -P models/ https://allennlp.s3.amazonaws.com/models/elmo-constituency-parser-2020.02.10.tar.gz

# Build submodules
WORKDIR /root/CarpetFuzz/fuzzer
RUN make clean all
WORKDIR /root/CarpetFuzz/pict
RUN cmake -DCMAKE_BUILD_TYPE=Release -S . -B build && cmake --build build
WORKDIR /root/CarpetFuzz/pict/build
RUN ctest -v

ENV CarpetFuzz=/root/CarpetFuzz

# Build libtiff for test
RUN mkdir /root/programs
WORKDIR /root/programs

RUN git clone https://gitlab.com/libtiff/libtiff libtiff; cd libtiff; git reset --hard b51bb157123264e26d34c09cc673d213aea61fc7; \
    bash ./autogen.sh; \
    CC=${CarpetFuzz}/fuzzer/afl-clang-fast CXX=${CarpetFuzz}/fuzzer/afl-clang-fast++ ./configure --prefix=$PWD/build_carpetfuzz --disable-shared; \
    make -j;make install;make clean; \
    mkdir input; cp ${CarpetFuzz}/fuzzer/testcases/images/tiff/not_kitty.tiff input/

# Finished
WORKDIR /root/CarpetFuzz