# Shared LibreOffice tree: build slots

These rules apply to every stream that builds in the shared tree, `upstream/libreoffice`, while
working on patches that are not in `series` yet.

## The slot

1. Take the lock for the whole slot: `flock /home/office/build/locks/lo-make.lock <script>`. Run
   builds as `hstbuild`.
2. Before changing anything, prove that the files your patches touch are at the series state. Take
   the series from origin, or from `s0/integration`, never from a `/home/office` checkout. Every
   series patch that touches those files must reverse-apply at fuzz 0, in reverse order, on a copy.
3. Dry-run your whole chain at fuzz 0 on a copy, then apply it.
4. Build in three separate `make` invocations, in this order:
   1. `make udkapi.build offapi.build oovbaapi.build`
   2. the modules your patches touch, plus `Library_merged` (vcl, sfx2 and svx live in libmergedlo)
   3. modules that link against libmergedlo, such as `sw.build`, `sc.build` and `sd.build`
5. Copy what you need into a private instdir copy. Break hard links to every file you take: use
   `cp --remove-destination`, then `chown hstbuild`.
6. Reverse your patches. Run the same three build steps again to restore the shared instdir, and do
   this even when the patched build failed. Check every touched file, `.po` files included, against
   the copy from step 2.

## Why the API headers go first, in their own invocation

A `Library_merged` build relinks `instdir/sdk/bin/cppumaker`, `libreglo` and `libunoidllo`. That
leaves `workdir/UnoApiHeadersTarget/offapi/normal.done` stale.

The next module build, for example `make vcl.build`, then remakes the offapi headers from inside
that module's sub-make. There cppumaker is called without `-X udkapi.rdb`, and the build fails with:

```
ERROR: Unknown entity 'com.sun.star.lang.EventObject'
```

The shared instdir then keeps the patched libraries until someone repairs it (2026-11-07). Building
`udkapi`, `offapi` and `oovbaapi` as modules first, in their own invocation, remakes the headers with
the right dependencies.

## Incremental-build gaps

Neither `make build` nor a module build remakes:

- the vi `.mo` catalogues;
- the translated registry, `registry_vi.xcd`.

A new `sd.component` entry also does not reach `instdir/program/services/services.rdb`.

For a private test copy, use one of these:

- compile the catalogue with `msgfmt` from the patched `.po`;
- run `make AllLangMoTarget_<module>.clean` first.

A clean CI build compiles all of these.
