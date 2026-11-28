# Runs on the Taster, fed by strace. Condenses the syscall stream into a short
# summary so a script that deletes a million files does not produce a million
# lines. It is already in memory when the meal starts, so it survives rm -rf /.
/connect\(/ && /sin6?_(addr|port)/ {
  if (match($0, /inet_addr\("[^"]+"\)/)) ip = substr($0, RSTART + 11, RLENGTH - 13)
  else if (match($0, /inet_pton\(AF_INET6, "[^"]+"/)) ip = substr($0, RSTART + 21, RLENGTH - 22)
  else ip = "?"
  port = "?"
  if (match($0, /htons\([0-9]+\)/)) port = substr($0, RSTART + 6, RLENGTH - 7)
  if (ip != "127.0.0.1" && ip != "::1" && !((ip ":" port) in seen)) { seen[ip ":" port] = 1; print "@T connect " ip ":" port }
  next
}
/execve\(/ && !/ENOENT/ {
  nexec++
  if (nexec <= 40 && match($0, /execve\("[^"]+", \[.*\]/)) print "@T exec " substr($0, RSTART + 7, (RLENGTH > 200 ? 200 : RLENGTH) - 7)
  next
}
/unlink(at)?\(/ && / = 0/ {
  ndel++
  if (ndel <= 15 && match($0, /"[^"]+"/)) print "@T delete " substr($0, RSTART, RLENGTH)
  next
}
/openat\(/ && /O_(WRONLY|RDWR)/ && /O_(CREAT|TRUNC|APPEND)/ && !/ = -1/ {
  if (match($0, /"[^"]+"/)) {
    f = substr($0, RSTART, RLENGTH)
    if (f !~ /^"\/dev\// && !(f in wrote)) { wrote[f] = 1; nwr++; if (nwr <= 40) print "@T write " f }
  }
  next
}
/rename(at2?)?\(/ && / = 0/ { nren++; if (nren <= 10) print "@T rename " $0; next }
/chmod(at)?\(/ && / = 0/ { nch++; if (nch <= 10 && match($0, /"[^"]+"/)) print "@T chmod " substr($0, RSTART, RLENGTH); next }
END {
  print "@T totals exec=" nexec + 0 " deleted=" ndel + 0 " written=" nwr + 0 " renamed=" nren + 0 " chmod=" nch + 0
}
