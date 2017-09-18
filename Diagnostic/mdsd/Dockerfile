FROM ubuntu:trusty

RUN apt-get update && apt-get install -y software-properties-common

RUN apt-get update && \
    apt-get install -y sudo apt-utils openssh-server wget unzip git build-essential libtool && \
    apt-get upgrade -y && apt-get dist-upgrade -y

EXPOSE 22

RUN update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-4.8 50 && \
    update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-4.8 50

RUN apt-get update && \
    apt-get install -y psmisc libxml++2.6-dev uuid-dev python-software-properties zlib1g-dev \
                       libssl1.0.0 libssl-dev cmake rpm liblzma-dev libjson-c-dev libjson-c2

RUN apt-get update && ver=1.55 && \
    apt-get install -y libboost$ver-dev libboost-system$ver-dev libboost-thread$ver-dev \
                       libboost-filesystem$ver-dev libboost-random$ver-dev libboost-locale$ver-dev \
		       libboost-regex$ver-dev libboost-iostreams$ver-dev libboost-log$ver-dev

RUN apt-get update && ver=1.55.0 && \
    apt-get install -y libboost-system$ver libboost-thread$ver libboost-filesystem$ver \
                       libboost-random$ver libboost-locale$ver libboost-regex$ver \
		       libboost-iostreams$ver libboost-log$ver

ADD azure.list /etc/apt/sources.list.d/azure.list
RUN apt-key adv --keyserver packages.microsoft.com --recv-keys B02C46DF417A0893 && \
    apt-get install apt-transport-https

RUN apt-get update && \
    apt-get install -y libcpprest-dev libazurestorage-dev libomi-dev libcpprest \
                       libazurestorage omi libbond-dev
