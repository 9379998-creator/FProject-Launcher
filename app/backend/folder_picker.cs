using System;
using System.IO;
using System.Runtime.InteropServices;

namespace FeroLauncher {
    static class Program {
        [DllImport("user32.dll")]
        private static extern IntPtr GetForegroundWindow();

        [DllImport("shell32.dll", CharSet = CharSet.Auto)]
        private static extern int SHCreateItemFromParsingName(
            [MarshalAs(UnmanagedType.LPWStr)] string pszPath,
            IntPtr pbc,
            ref Guid riid,
            [MarshalAs(UnmanagedType.Interface)] out object ppv);

        [ComImport]
        [Guid("DC1C5A9C-E88A-4DDE-A5A1-60F82A20AEF7")]
        [ClassInterface(ClassInterfaceType.None)]
        private class FileOpenDialogInternal { }

        [ComImport]
        [Guid("d57c7288-d4a4-47e3-8021-2d880149e466")]
        [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        private interface IFileOpenDialog {
            [PreserveSig] int Show(IntPtr parent);
            void SetFileTypes();
            void SetFileTypeIndex();
            void GetFileTypeIndex();
            void Advise();
            void Unadvise();
            void SetOptions(uint fos);
            void GetOptions(out uint pfos);
            void SetDefaultFolder(object psi);
            void SetFolder(object psi);
            void GetFolder(out object ppsi);
            void GetCurrentSelection(out object ppsi);
            void SetFileName([MarshalAs(UnmanagedType.LPWStr)] string pszName);
            void GetFileName([MarshalAs(UnmanagedType.LPWStr)] out string pszName);
            void SetTitle([MarshalAs(UnmanagedType.LPWStr)] string pszTitle);
            void SetOkButtonLabel([MarshalAs(UnmanagedType.LPWStr)] string pszText);
            void SetFileNameLabel([MarshalAs(UnmanagedType.LPWStr)] string pszLabel);
            void GetResult(out IShellItem ppsi);
        }

        [ComImport]
        [Guid("43826d1e-e718-42ee-bc55-a1e261c37bfe")]
        [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        private interface IShellItem {
            void BindToHandler();
            void GetParent();
            void GetDisplayName(uint sigdnName, [MarshalAs(UnmanagedType.LPWStr)] out string ppszName);
            void GetAttributes();
            void Compare();
        }

        [STAThread]
        static int Main(string[] args) {
            try {
                var dlg = (IFileOpenDialog)new FileOpenDialogInternal();
                try {
                    // FOS_PICKFOLDERS (0x20) | FOS_FORCEFILESYSTEM (0x40) | FOS_PATHMUSTEXIST (0x800)
                    uint options = 0x00000020 | 0x00000040 | 0x00000800;
                    dlg.SetOptions(options);
                    dlg.SetTitle("Выберите папку объекта - FERO Launcher");

                    if (args.Length > 0 && !string.IsNullOrEmpty(args[0]) && Directory.Exists(args[0])) {
                        Guid guid = new Guid("43826d1e-e718-42ee-bc55-a1e261c37bfe");
                        object folderItem;
                        if (SHCreateItemFromParsingName(args[0], IntPtr.Zero, ref guid, out folderItem) == 0) {
                            dlg.SetFolder(folderItem);
                        }
                    }

                    IntPtr owner = GetForegroundWindow();
                    int hr = dlg.Show(owner);
                    if (hr == 0) {
                        IShellItem item;
                        dlg.GetResult(out item);
                        string path;
                        item.GetDisplayName(0x80058000, out path); // SIGDN_FILESYSPATH
                        Console.OutputEncoding = System.Text.Encoding.UTF8;
                        Console.WriteLine(path);
                        return 0;
                    }
                    return 1; // User cancelled
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
