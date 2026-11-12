// SPDX-License-Identifier: AGPL-3.0-only
// Native helpers for scripts/windows/sign-msi.ps1, compiled at run time with Add-Type (no SDK needed):
//   HstMsiDb     - Windows Installer database access through msi.dll (queries, parameterised updates,
//                  binary streams to and from files, file hashes). The COM automation layer cannot move
//                  binary stream data, so this uses the C API.
//   HstAuthenticode - Authenticode signing through mssign32.dll (SignerSignEx2) with SHA-256 digests and a
//                  separate RFC 3161 timestamp (SignerTimeStampEx2), the same calls the SDK signing tool makes.
// The signing key is never read: the certificate context is handed to the system, which asks the key's
// provider (for a USB token: its own PIN dialog) to sign.
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography.X509Certificates;
using System.Text;

public sealed class HstMsiDb : IDisposable
{
    const uint ERROR_SUCCESS = 0, ERROR_MORE_DATA = 234, ERROR_NO_MORE_ITEMS = 259;
    const int MSIMODIFY_ASSIGN = 3;
    IntPtr handle;

    [DllImport("msi.dll", CharSet = CharSet.Unicode)] static extern uint MsiOpenDatabaseW(string path, IntPtr persist, out IntPtr db);
    [DllImport("msi.dll", CharSet = CharSet.Unicode)] static extern uint MsiDatabaseOpenViewW(IntPtr db, string query, out IntPtr view);
    [DllImport("msi.dll", CharSet = CharSet.Unicode)] static extern int MsiDatabaseIsTablePersistentW(IntPtr db, string table);
    [DllImport("msi.dll")] static extern uint MsiDatabaseCommit(IntPtr db);
    [DllImport("msi.dll")] static extern uint MsiViewExecute(IntPtr view, IntPtr record);
    [DllImport("msi.dll")] static extern uint MsiViewFetch(IntPtr view, out IntPtr record);
    [DllImport("msi.dll")] static extern uint MsiViewModify(IntPtr view, int mode, IntPtr record);
    [DllImport("msi.dll")] static extern uint MsiViewClose(IntPtr view);
    [DllImport("msi.dll")] static extern uint MsiCloseHandle(IntPtr handle);
    [DllImport("msi.dll")] static extern IntPtr MsiCreateRecord(uint fields);
    [DllImport("msi.dll")] static extern uint MsiRecordGetFieldCount(IntPtr record);
    [DllImport("msi.dll", CharSet = CharSet.Unicode)] static extern uint MsiRecordGetStringW(IntPtr record, uint field, StringBuilder value, ref uint length);
    [DllImport("msi.dll", CharSet = CharSet.Unicode)] static extern uint MsiRecordSetStringW(IntPtr record, uint field, string value);
    [DllImport("msi.dll")] static extern uint MsiRecordSetInteger(IntPtr record, uint field, int value);
    [DllImport("msi.dll", CharSet = CharSet.Unicode)] static extern uint MsiRecordSetStreamW(IntPtr record, uint field, string path);
    [DllImport("msi.dll")] static extern uint MsiRecordReadStream(IntPtr record, uint field, byte[] buffer, ref uint length);
    [DllImport("msi.dll", CharSet = CharSet.Unicode)] static extern uint MsiGetFileHashW(string path, uint options, ref FileHashInfo hash);

    [StructLayout(LayoutKind.Sequential)]
    struct FileHashInfo { public uint Size, Part1, Part2, Part3, Part4; }

    static void Check(uint rc, string what)
    {
        if (rc != ERROR_SUCCESS) throw new Win32Exception((int)rc, what + " failed (" + rc + ")");
    }

    public HstMsiDb(string path, bool write)
    {
        Check(MsiOpenDatabaseW(path, new IntPtr(write ? 1 : 0), out handle), "open " + path);  // 1: transacted
    }

    public bool HasTable(string table) { return MsiDatabaseIsTablePersistentW(handle, table) == 1; }

    public void Commit() { Check(MsiDatabaseCommit(handle), "commit"); }

    public void Dispose()
    {
        if (handle != IntPtr.Zero) { MsiCloseHandle(handle); handle = IntPtr.Zero; }
    }

    // A view executed with ? parameters (int or string values).
    IntPtr Open(string sql, object[] args)
    {
        IntPtr view;
        Check(MsiDatabaseOpenViewW(handle, sql, out view), "query " + sql);
        IntPtr record = IntPtr.Zero;
        try
        {
            if (args != null && args.Length > 0)
            {
                record = MsiCreateRecord((uint)args.Length);
                for (int i = 0; i < args.Length; i++)
                {
                    if (args[i] is int) Check(MsiRecordSetInteger(record, (uint)i + 1, (int)args[i]), "parameter");
                    else Check(MsiRecordSetStringW(record, (uint)i + 1, Convert.ToString(args[i])), "parameter");
                }
            }
            Check(MsiViewExecute(view, record), "execute " + sql);
        }
        catch { MsiCloseHandle(view); throw; }
        finally { if (record != IntPtr.Zero) MsiCloseHandle(record); }
        return view;
    }

    static string GetString(IntPtr record, uint field)
    {
        uint length = 256;
        var value = new StringBuilder((int)length);
        uint rc = MsiRecordGetStringW(record, field, value, ref length);
        if (rc == ERROR_MORE_DATA)
        {
            length++;
            value = new StringBuilder((int)length);
            rc = MsiRecordGetStringW(record, field, value, ref length);
        }
        Check(rc, "read field");
        return value.ToString();
    }

    // Every row of a query that selects no stream columns, as strings.
    public List<string[]> Query(string sql, params object[] args)
    {
        var rows = new List<string[]>();
        IntPtr view = Open(sql, args);
        try
        {
            while (true)
            {
                IntPtr record;
                uint rc = MsiViewFetch(view, out record);
                if (rc == ERROR_NO_MORE_ITEMS) break;
                Check(rc, "fetch");
                try
                {
                    uint count = MsiRecordGetFieldCount(record);
                    var row = new string[count];
                    for (uint i = 0; i < count; i++) row[i] = GetString(record, i + 1);
                    rows.Add(row);
                }
                finally { MsiCloseHandle(record); }
            }
        }
        finally { MsiViewClose(view); MsiCloseHandle(view); }
        return rows;
    }

    public void Execute(string sql, params object[] args)
    {
        IntPtr view = Open(sql, args);
        MsiViewClose(view);
        MsiCloseHandle(view);
    }

    // Writes the Data stream of the row `Name` = key in a Binary-like table (or _Streams) to a file.
    public long ExportStream(string table, string key, string path)
    {
        IntPtr view = Open("SELECT `Data` FROM `" + table + "` WHERE `Name` = ?", new object[] { key });
        try
        {
            IntPtr record;
            uint rc = MsiViewFetch(view, out record);
            if (rc == ERROR_NO_MORE_ITEMS) throw new InvalidOperationException(table + " has no row " + key);
            Check(rc, "fetch stream");
            long total = 0;
            try
            {
                using (var output = File.Create(path))
                {
                    var buffer = new byte[1 << 20];
                    while (true)
                    {
                        uint length = (uint)buffer.Length;
                        Check(MsiRecordReadStream(record, 1, buffer, ref length), "read stream " + key);
                        if (length == 0) break;
                        output.Write(buffer, 0, (int)length);
                        total += length;
                    }
                }
            }
            finally { MsiCloseHandle(record); }
            return total;
        }
        finally { MsiViewClose(view); MsiCloseHandle(view); }
    }

    // Inserts or replaces the Data stream of row `Name` = key with the content of a file.
    public void ImportStream(string table, string key, string path)
    {
        IntPtr view = Open("SELECT `Name`, `Data` FROM `" + table + "`", null);
        IntPtr record = MsiCreateRecord(2);
        try
        {
            Check(MsiRecordSetStringW(record, 1, key), "stream name");
            Check(MsiRecordSetStreamW(record, 2, path), "stream data " + path);
            Check(MsiViewModify(view, MSIMODIFY_ASSIGN, record), "write stream " + key);
        }
        finally { MsiCloseHandle(record); MsiViewClose(view); MsiCloseHandle(view); }
    }

    // The four MsiFileHash parts of an unversioned file.
    public static int[] FileHash(string path)
    {
        var info = new FileHashInfo { Size = (uint)Marshal.SizeOf(typeof(FileHashInfo)) };
        Check(MsiGetFileHashW(path, 0, ref info), "hash " + path);
        return new[] { (int)info.Part1, (int)info.Part2, (int)info.Part3, (int)info.Part4 };
    }
}

public static class HstAuthenticode
{
    const uint SIGNER_SUBJECT_FILE = 1, SIGNER_CERT_STORE = 2, SIGNER_CERT_POLICY_CHAIN_NO_ROOT = 8;
    const uint SIGNER_AUTHCODE_ATTR = 1, SIGNER_TIMESTAMP_RFC3161 = 2, CALG_SHA_256 = 0x800c;
    const uint CRYPT_ACQUIRE_CACHE_FLAG = 1, CRYPT_ACQUIRE_ALLOW_NCRYPT_KEY_FLAG = 0x10000;

    [StructLayout(LayoutKind.Sequential)] struct FileInfo { public uint cbSize; public IntPtr pwszFileName; public IntPtr hFile; }
    [StructLayout(LayoutKind.Sequential)] struct SubjectInfo { public uint cbSize; public IntPtr pdwIndex; public uint dwSubjectChoice; public IntPtr pSignerFileInfo; }
    [StructLayout(LayoutKind.Sequential)] struct CertStoreInfo { public uint cbSize; public IntPtr pSigningCert; public uint dwCertPolicy; public IntPtr hCertStore; }
    [StructLayout(LayoutKind.Sequential)] struct SignerCert { public uint cbSize; public uint dwCertChoice; public IntPtr pCertStoreInfo; public IntPtr hwnd; }
    [StructLayout(LayoutKind.Sequential)] struct AttrAuthcode { public uint cbSize; public int fCommercial; public int fIndividual; public IntPtr pwszName; public IntPtr pwszInfo; }
    [StructLayout(LayoutKind.Sequential)] struct SignatureInfo { public uint cbSize; public uint algidHash; public uint dwAttrChoice; public IntPtr pAttrAuthcode; public IntPtr psAuthenticated; public IntPtr psUnauthenticated; }

    [DllImport("mssign32.dll", CharSet = CharSet.Unicode)]
    static extern int SignerSignEx2(uint flags, IntPtr subject, IntPtr cert, IntPtr signature, IntPtr provider,
        uint timestampFlags, IntPtr timestampOid, IntPtr timestampUrl, IntPtr request, IntPtr sipData,
        out IntPtr context, IntPtr cryptoPolicy, IntPtr reserved);
    [DllImport("mssign32.dll", CharSet = CharSet.Unicode)]
    static extern int SignerTimeStampEx2(uint flags, IntPtr subject, string url, uint algId, IntPtr request, IntPtr sipData, out IntPtr context);
    [DllImport("mssign32.dll")] static extern int SignerFreeSignerContext(IntPtr context);
    [DllImport("crypt32.dll", SetLastError = true)]
    static extern bool CryptAcquireCertificatePrivateKey(IntPtr cert, uint flags, IntPtr reserved, out IntPtr key, out uint keySpec, out bool callerFree);

    // Opens the key once and caches the handle on the certificate context, so a token that keeps its login
    // per key handle asks for the PIN once for the whole run rather than once per file.
    public static void OpenKey(X509Certificate2 certificate)
    {
        IntPtr key; uint spec; bool free;
        if (!CryptAcquireCertificatePrivateKey(certificate.Handle, CRYPT_ACQUIRE_CACHE_FLAG | CRYPT_ACQUIRE_ALLOW_NCRYPT_KEY_FLAG, IntPtr.Zero, out key, out spec, out free))
            throw new Win32Exception(Marshal.GetLastWin32Error(), "cannot open the signing key (token connected and unlocked?)");
    }

    sealed class Subject : IDisposable
    {
        readonly List<IntPtr> blocks = new List<IntPtr>();
        public readonly IntPtr Pointer;

        public IntPtr Alloc(object structure)
        {
            IntPtr block = Marshal.AllocHGlobal(Marshal.SizeOf(structure));
            blocks.Add(block);
            Marshal.StructureToPtr(structure, block, false);
            return block;
        }

        public IntPtr Text(string value)
        {
            IntPtr block = Marshal.StringToHGlobalUni(value);
            blocks.Add(block);
            return block;
        }

        public Subject(string path)
        {
            IntPtr index = Marshal.AllocHGlobal(4);
            blocks.Add(index);
            Marshal.WriteInt32(index, 0);
            var file = new FileInfo { cbSize = (uint)Marshal.SizeOf(typeof(FileInfo)), pwszFileName = Text(path) };
            Pointer = Alloc(new SubjectInfo { cbSize = (uint)Marshal.SizeOf(typeof(SubjectInfo)), pdwIndex = index,
                                              dwSubjectChoice = SIGNER_SUBJECT_FILE, pSignerFileInfo = Alloc(file) });
        }

        public void Dispose() { foreach (IntPtr block in blocks) Marshal.FreeHGlobal(block); blocks.Clear(); }
    }

    static void Check(int hr, string what)
    {
        if (hr != 0) throw new Win32Exception(hr, what + " failed (0x" + hr.ToString("X8") + ")");
    }

    // Replaces any signature of a PE file, cabinet or MSI with a SHA-256 signature by `certificate`
    // (chain without root), describing it as `name`/`info` (shown in elevation prompts for MSI files).
    public static void Sign(string path, X509Certificate2 certificate, string name, string info)
    {
        using (var subject = new Subject(path))
        {
            var store = new CertStoreInfo { cbSize = (uint)Marshal.SizeOf(typeof(CertStoreInfo)), pSigningCert = certificate.Handle,
                                            dwCertPolicy = SIGNER_CERT_POLICY_CHAIN_NO_ROOT };
            var cert = new SignerCert { cbSize = (uint)Marshal.SizeOf(typeof(SignerCert)), dwCertChoice = SIGNER_CERT_STORE,
                                        pCertStoreInfo = subject.Alloc(store) };
            var attr = new AttrAuthcode { cbSize = (uint)Marshal.SizeOf(typeof(AttrAuthcode)),
                                          pwszName = string.IsNullOrEmpty(name) ? IntPtr.Zero : subject.Text(name),
                                          pwszInfo = string.IsNullOrEmpty(info) ? IntPtr.Zero : subject.Text(info) };
            var signature = new SignatureInfo { cbSize = (uint)Marshal.SizeOf(typeof(SignatureInfo)), algidHash = CALG_SHA_256,
                                                dwAttrChoice = SIGNER_AUTHCODE_ATTR, pAttrAuthcode = subject.Alloc(attr) };
            IntPtr context;
            Check(SignerSignEx2(0, subject.Pointer, subject.Alloc(cert), subject.Alloc(signature), IntPtr.Zero, 0, IntPtr.Zero,
                                IntPtr.Zero, IntPtr.Zero, IntPtr.Zero, out context, IntPtr.Zero, IntPtr.Zero), "sign " + path);
            if (context != IntPtr.Zero) SignerFreeSignerContext(context);
        }
    }

    // Adds an RFC 3161 SHA-256 timestamp from `url` to the signature of an already signed file.
    public static void Timestamp(string path, string url)
    {
        using (var subject = new Subject(path))
        {
            IntPtr context;
            Check(SignerTimeStampEx2(SIGNER_TIMESTAMP_RFC3161, subject.Pointer, url, CALG_SHA_256, IntPtr.Zero, IntPtr.Zero,
                                     out context), "timestamp " + path);
            if (context != IntPtr.Zero) SignerFreeSignerContext(context);
        }
    }
}
