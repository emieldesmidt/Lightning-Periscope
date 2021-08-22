# Periscope [WIP, please ignore for now. Complete setup instructions will follow]

## Setup
The local development of this project has been done with Polar, see https://lightningpolar.com/. For ease of use, the paths to the relevant files of the docker nodes are best stored in a file named creds.txt in the root directory. 

## Setup and Installation

Lnd uses the gRPC protocol for communication with clients like lncli. gRPC is
based on protocol buffers and as such, you will need to compile the lnd proto
file in Python before you can use it to communicate with lnd.

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

After following these steps, two files `rpc_pb2.py` and `rpc_pb2_grpc.py` will
be generated. These files will be imported in your project anytime you use
Python gRPC.

### Generating RPC modules for subservers

If you want to use any of the subservers' functionality, you also need to
generate the python modules for them.

For example, if you want to generate the RPC modules for the `Router` subserver
(located/defined in `routerrpc/router.proto`), you need to run the following two
extra steps (after completing all 6 step described above) to get the
`router_pb2.py` and `router_pb2_grpc.py`:

```shell
lnd ⛰  curl -o router.proto -s https://raw.githubusercontent.com/lightningnetwork/lnd/master/lnrpc/routerrpc/router.proto
lnd ⛰  python -m grpc_tools.protoc --proto_path=googleapis:. --python_out=. --grpc_python_out=. router.proto
```
