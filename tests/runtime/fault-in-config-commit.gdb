# Test-only (check-close-crash-handler-linux.py): stop the office in a configuration commit, let it take the
# configuration lock (first osl_acquireMutex inside the commit), then make that thread fault at address 0.
set pagination off
set confirm off
handle SIGSEGV nostop noprint pass
handle SIGPIPE nostop noprint pass
break _ZNK10comphelper20ConfigurationChanges6commitEv
continue
echo HIT-commit\n
delete
break osl_acquireMutex
continue
echo HIT-acquire\n
delete
finish
echo LOCK-HELD\n
bt 12
set var $pc = 0
detach
quit
