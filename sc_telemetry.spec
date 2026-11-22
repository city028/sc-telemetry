# PyInstaller build for SC Telemetry.
#   pip install -r requirements.txt
#   .\build.ps1            (this spec, then the installer around its output)
# A folder, not one file: the installer delivers it, and starting does not
# unpack the whole program to a temp folder every time.

datas = [
    ("ui/index.html", "ui"),                    # the window's page
    ("proto/types.proto.desc", "proto"),        # message types, as taken from StarCitizen.exe
    ("proto/api.proto.desc", "proto"),
    ("icon.ico", "."),
]

a = Analysis(["app/__main__.py"], pathex=["."], datas=datas)
pyz = PYZ(a.pure)
# No console: a console program opens an empty black window at every start.
# Errors go to %LocalAppData%\SC Telemetry\sc-telemetry.log instead.
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="sc-telemetry",
          console=False, upx=False, icon="icon.ico")
coll = COLLECT(exe, a.binaries, a.datas, name="sc-telemetry", upx=False)
