 #!/bin/bash

# courtesty of https://unix.stackexchange.com/a/259254
function bytesToHumanReadable() {
    local i=${1:-0} d="" s=0 S=("Bytes" "KiB" "MiB" "GiB" "TiB" "PiB" "EiB" "YiB" "ZiB")
    while ((i > 1024 && s < ${#S[@]}-1)); do
        printf -v d ".%02d" $((i % 1024 * 100 / 1024))
        i=$((i / 1024))
        s=$((s + 1))
    done
    echo "$i$d ${S[$s]}"
}


function bench() {
    results=($(curl -so /dev/null -s $1 --proxy 127.0.0.1:8742 -w '%{size_download} %{time_total} %{speed_download} %{time_starttransfer}' --insecure))
    echo "${results[0]} ${results[1]} ${results[2]} ${results[3]}"
}


function bench_n() {

    s_sum=0
    t_sum=0
    
    for ((n=0;n<$1;n++))
    do
        res=$(bench $2)
        read -a resarr <<< $res

        time=${resarr[1]}
        speed=${resarr[2]}
        
        s_sum=$((s_sum + speed))
	t_sum=$((t_sum + time))
        echo $speed $time
        sleep 5
    done

    s_avg=$(bc <<< "scale=0;$s_sum/$1")
    s_readable_avg=$(bytesToHumanReadable $s_avg)

    t_avg=$(bc <<< "scale=0;$t_sum/$1")
    t_readable_avg=$(bc <<< "scale=2;$t_avg/1000000")
    
    echo $s_avg bytes per second, $s_readable_avg per second. Average duration was $t_readable_avg.

    
    # At own risk
    spd-say --wait "$(echo Done completing $1 iterations of $2 the average throughput was $readable_avg per second)"
}

# Loading wikipedia page on censorship
echo
echo Benchmarking performance with Github: https://github.com
bench_n $1 "https://github.com"

sleep 30

echo
echo Benchmarking performance with the BBC: https://www.bbc.com
bench_n $1 "https://www.bbc.com/"

sleep 30

echo
echo Benchmarking performance with Wikipedia: https://en.wikipedia.org/wiki/Censorship 
bench_n $1 "https://en.wikipedia.org/wiki/Censorship"
