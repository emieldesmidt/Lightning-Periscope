# Periscope
Periscope is a protocol that allows for tunneling of internet traffic between two hosts over a stream of micro-transactions that are embedded with data. The Periscope protocol has clients for two different types of hosts: Submarine nodes wishing to tunnel their internet traffic, as well as Periscope nodes who offer tunneling services.
The project in front of you serves as a demo implementation. Please use testnet or local testbeds only, avoid the real Lightning Network as it could result in a loss of funds.


## Setup and Installation

LND uses the gRPC protocol for communication with clients like lncli. gRPC is based on protocol buffers and as such, you will need to compile the lnd protofile in Python before you can use it to communicate with lnd.

1. Create a virtual environment for your project
    ```shell
    ⛰  virtualenv lnd
    ```
2. Activate the virtual environment
    ```shell
    ⛰  source lnd/bin/activate
    ```
3. Install dependencies (googleapis-common-protos is required due to the use of
  google/api/annotations.proto)
    ```shell
    lnd ⛰  pip install grpcio grpcio-tools googleapis-common-protos
    ```
4. Clone the google api's repository (required due to the use of
  google/api/annotations.proto)
    ```shell
    lnd ⛰  git clone https://github.com/googleapis/googleapis.git
    ```
5. Copy the lnd rpc.proto file (you'll find this at
  [lnrpc/rpc.proto](https://github.com/lightningnetwork/lnd/blob/master/lnrpc/rpc.proto))
  or just download it
    ```shell
    lnd ⛰  curl -o rpc.proto -s https://raw.githubusercontent.com/lightningnetwork/lnd/master/lnrpc/rpc.proto
    ```
6. Compile the proto file
    ```shell
    lnd ⛰  python -m  -m grpc_tools.protoc --proto_path=./googleapis:. --python_out=. --grpc_python_out=. rpc.proto
    ```

After following these steps, two files `rpc_pb2.py` and `rpc_pb2_grpc.py` will be generated. We also need router functionality; you need to run the following two
extra steps (after completing all 6 step described above) to get the `router_pb2.py` and `router_pb2_grpc.py`:

```shell
lnd ⛰  curl -o router.proto -s https://raw.githubusercontent.com/lightningnetwork/lnd/master/lnrpc/routerrpc/router.proto
lnd ⛰  python -m grpc_tools.protoc --proto_path=googleapis:. --python_out=. --grpc_python_out=. router.proto
```

## Connecting to the Lightning Network.
The local development of this project has been done with Polar, see https://lightningpolar.com/. Polar allows for ultra-fast spinning up of Lightnign regtest networks, and comes with docker clients for all common Lightning implementations as well as a Bitcoin backend. By using Polar you can avoid the time-consuming testnet. 

Alternatively you can also install your Bitcoin deamon of choice and install LND directly on the host itself. For instructions see https://bitcoin.org/en/full-node and https://docs.lightning.engineering/lightning-network-tools/lnd/get-started-with-lnd .

### Configuring LND
For Periscope to work you need to have your LND Lightnign client configured with the new keysend method. This will allow for spontaneous payments, which is essential for the workings of the protocol.
For docker nodes, launch with the following:
```
lnd
  --accept-keysend
  --noseedbackup
  --trickledelay=5000
  --alias={{name}}
  --externalip={{name}}
  --tlsextradomain={{name}}
  --tlsextradomain={{containerName}}
  --listen=0.0.0.0:9735
  --rpclisten=0.0.0.0:10009
  --restlisten=0.0.0.0:8080
  --bitcoin.active
  --bitcoin.regtest
  --bitcoin.node=bitcoind
  --bitcoind.rpchost={{backendName}}
  --bitcoind.rpcuser={{rpcUser}}
  --bitcoind.rpcpass={{rpcPass}}
  --bitcoind.zmqpubrawblock=tcp://{{backendName}}:28334
  --bitcoind.zmqpubrawtx=tcp://{{backendName}}:28335
```

For a normal LND node:

```
listen=0.0.0.0:9735
listen=[::1]:9736

accept-keysend=true

[Bitcoin]
bitcoin.testnet=true
bitcoin.node=bitcoind
bitcoin.active=true

[Bitcoind]
bitcoind.dir=~/.bitcoin/testnet3
bitcoind.rpcuser=[username]
bitcoind.rpcpass=[password]
bitcoind.zmqpubrawblock=tcp://127.0.0.1:28332
bitcoind.zmqpubrawtx=tcp://127.0.0.1:28333
```

### Configuring the protocol
In order for the protocol to communicate with the LND client it needs to know a couple of things. You need to supply the following information:
- tls.cert filepath
- admin.macaroon filepath
- The node's public key
- The port it is running on

You can conveniently supply this information in the creds.txt file located in the project root. Add the aforementioned information in the following format:
```
[name],[tls.cert filepath],[admin.macaroon filepath],[public key],[port]
```
You can give it any name you want. You can use this name in the files submarine.py and periscope.py to quickly provide all the information. For example if you are the submarine node alice and you want to connect to bob on the Polar testbed:
```python
node = nodes['alice']
target_pk = nodes['bob']['pk']
