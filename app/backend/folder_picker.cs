using System;
using System.IO;
using System.Runtime.InteropServices;

namespace FeroLauncher {
    static class Program {
        [DllImport("user32.dll")]
        private static extern IntPtr GetForegroundWindow();

        [DllImport("shell32.dll", CharSet = CharSet.Auto, SetLastError = true)]
        private static extern int SHCreateItemFromParsingName(
            [MarshalAs(UnmanagedType.LPWStr)] string pszPath,
            IntPtr pbc,
            ref Guid riid,
            [MarshalAs(UnmanagedType.Interface)] out IShellItem ppv);

        [ComImport]
        [Guid("DC1C5A9C-E88A-4DDE-A5A1-60F82A20AEF7")]
        [ClassInterface(ClassInterfaceType.None)]
        private class FileOpenDialogInternal { }

        [ComImport]
        [Guid("42f85136-db7e-439c-85f1-e4075d135fc8")]
        [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        private interface IFileDialog {
            [PreserveSig] int Show(IntPtr parent);
            void SetFileTypes(uint cFileTypes, IntPtr rgFilterSpec);
            void SetFileTypeIndex(uint iFileType);
            void GetFileTypeIndex(out uint piFileType);
            void Advise(IntPtr pfde, out uint pdwCookie);
            void Unadvise(uint dwCookie);
            void SetOptions(uint fos);
            void GetOptions(out uint pfos);
            void SetDefaultFolder(IShellItem psi);
            void SetFolder(IShellItem psi);
            void GetFolder(out IShellItem ppsi);
            void GetCurrentSelection(out IShellItem ppsi);
            void SetFileName([MarshalAs(UnmanagedType.LPWStr)] string pszName);
            void GetFileName([MarshalAs(UnmanagedType.LPWStr)] out string pszName);
            void SetTitle([MarshalAs(UnmanagedType.LPWStr)] string pszTitle);
            void SetOkButtonLabel([MarshalAs(UnmanagedType.LPWStr)] string pszText);
            void SetFileNameLabel([MarshalAs(UnmanagedType.LPWStr)] string pszLabel);
            [PreserveSig] int GetResult(out IShellItem ppsi);
        }

        [ComImport]
        [Guid("43826d1e-e718-42ee-bc55-a1e261c37bfe")]
        [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        private interface IShellItem {
            void BindToHandler(IntPtr pbc, ref Guid bhid, ref Guid riid, out IntPtr ppv);
            void GetParent(out IShellItem ppsi);
            [PreserveSig] int GetDisplayName(uint sigdnName, [MarshalAs(UnmanagedType.LPWStr)] out string ppszName);
            void GetAttributes(uint sfgaoMask, out uint psfgaoAttribs);
            void Compare(IShellItem psi, uint hint, out int piOrder);
        }

        [STAThread]
        static int Main(string[] args) {
            try {
                if (Array.IndexOf(args, "--test") >= 0) {
                    Console.WriteLine("READY");
                    return 0;
                }

                var dlg = (IFileDialog)new FileOpenDialogInternal();
                try {
                    // FOS_PICKFOLDERS (0x20) | FOS_PATHMUSTEXIST (0x800) | FOS_NOCHANGEDIR (0x8)
                    // Note: Do NOT use FOS_FORCEFILESYSTEM (0x40) as it rejects Google Drive / Cloud namespace items!
                    uint options = 0x00000020 | 0x00000800 | 0x00000008;
                    dlg.SetOptions(options);
                    dlg.SetTitle("Выбор папки объекта - FERO Launcher");

                    string initialDir = null;
                    foreach (var a in args) {
                        if (!a.StartsWith("--") && Directory.Exists(a)) {
                            initialDir = a;
                            break;
                        }
                    }
                    if (!string.IsNullOrEmpty(initialDir)) {
                        Guid guid = new Guid("43826d1e-e718-42ee-bc55-a1e261c37bfe");
                        IShellItem folderItem;
                        if (SHCreateItemFromParsingName(initialDir, IntPtr.Zero, ref guid, out folderItem) == 0) {
                            dlg.SetFolder(folderItem);
                        }
                    }

                    IntPtr owner = GetForegroundWindow();
                    int hr = dlg.Show(owner);
                    if (hr == 0) {
                        IShellItem item;
                        if (dlg.GetResult(out item) == 0 && item != null) {
                            string path = null;
                            // 1. Try SIGDN_FILESYSPATH (0x80058000)
                            int hrName = item.GetDisplayName(0x80058000, out path);
                            // 2. Fallback to SIGDN_DESKTOPABSOLUTEPARSING (0x80028000) for Google Drive / Network drives
                            if (hrName != 0 || string.IsNullOrEmpty(path)) {
                                hrName = item.GetDisplayName(0x80028000, out path);
                            }
                            // 3. Fallback to SIGDN_NORMALDISPLAY (0x00000000)
                            if (hrName != 0 || string.IsNullOrEmpty(path)) {
                                hrName = item.GetDisplayName(0x00000000, out path);
                            }

                            if (!string.IsNullOrEmpty(path)) {
                                Console.OutputEncoding = new System.Text.UTF8Encoding(false);
                                Console.WriteLine(path);
                                return 0;
                            }
                        }
                    }
                    return 1; // User cancelled or closed window
                } finally {
                    Marshal.ReleaseComObject(dlg);
                }
            } catch (Exception ex) {
                Console.Error.WriteLine(ex.Message);
                return 2;
            }
        }
    }
}
