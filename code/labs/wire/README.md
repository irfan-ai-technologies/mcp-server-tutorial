# wire

Chapter 2 reads the protocol off the wire. This lab is what puts it there.

```bash
./capture.sh          # starts ledger, issues a request per method, writes transcripts/
```

The transcripts are committed, so the chapter can include real bytes and CI can tell when
they stop matching what the server does. Regenerate them whenever the server or the
protocol changes, and read the diff — that diff is the chapter's maintenance.

Only `curl` is used. A client library would hide the exact thing the chapter is about:
there is no session, no handshake, and no state between these requests.
