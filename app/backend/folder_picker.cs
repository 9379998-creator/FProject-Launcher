using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

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
            void SetDefaultFolder([MarshalAs(UnmanagedType.Interface)] IShellItem psi);
            void SetFolder([MarshalAs(UnmanagedType.Interface)] IShellItem psi);
            void GetFolder([MarshalAs(UnmanagedType.Interface)] out IShellItem ppsi);
            void GetCurrentSelection([MarshalAs(UnmanagedType.Interface)] out IShellItem ppsi);
            void SetFileName([MarshalAs(UnmanagedType.LPWStr)] string pszName);
            void GetFileName([MarshalAs(UnmanagedType.LPWStr)] out string pszName);
            void SetTitle([MarshalAs(UnmanagedType.LPWStr)] string pszTitle);
            void SetOkButtonLabel([MarshalAs(UnmanagedType.LPWStr)] string pszText);
            void SetFileNameLabel([MarshalAs(UnmanagedType.LPWStr)] string pszLabel);
            void GetResult([MarshalAs(UnmanagedType.Interface)] out IShellItem ppsi);
        }

        [ComImport]
        [Guid("43826d1e-e718-42ee-bc55-a1e261c37bfe")]
        [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        private interface IShellItem {
            void BindToHandler(IntPtr pbc, ref Guid bhid, ref Guid riid, out IntPtr ppv);
            void GetParent([MarshalAs(UnmanagedType.Interface)] out IShellItem ppsi);
            [PreserveSig] int GetDisplayName(uint sigdnName, out IntPtr ppszName);
            void GetAttributes(uint sfgaoMask, out uint psfgaoAttribs);
            void Compare([MarshalAs(UnmanagedType.Interface)] IShellItem psi, uint hint, out int piOrder);
        }

        static void Log(string msg) {
            try {
                string localApp = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
                string logDir = Path.Combine(localApp, @"FEngineering_Launcher\runtime\logs");
                if (!Directory.Exists(logDir)) Directory.CreateDirectory(logDir);
                string logFile = Path.Combine(logDir, "folder_picker.log");
                File.AppendAllText(logFile, string.Format("[{0:yyyy-MM-dd HH:mm:ss}] {1}\r\n", DateTime.Now, msg));
            } catch { }
        }

        [STAThread]
        static int Main(string[] args) {
            try {
                if (Array.IndexOf(args, "--test") >= 0) {
                    try {
                        using (var stdout = Console.OpenStandardOutput()) {
                            byte[] bytes = new UTF8Encoding(false).GetBytes("READY\r\n");
                            stdout.Write(bytes, 0, bytes.Length);
                            stdout.Flush();
                        }
                    } catch {
                        Console.WriteLine("READY");
                    }
                    return 0;
                }

                Log("folder_picker launched with args: " + string.Join(" ", args));

                string outFile = null;
                string initialDir = null;
                for (int i = 0; i < args.Length; i++) {
                    if (args[i] == "--out-file" && i + 1 < args.Length) {
                        outFile = args[i + 1];
                        i++;
                    } else if (!args[i].StartsWith("--") && Directory.Exists(args[i])) {
                        initialDir = args[i];
                    }
                }

                var dlg = (IFileDialog)new FileOpenDialogInternal();
                try {
                    // FOS_PICKFOLDERS (0x20) | FOS_PATHMUSTEXIST (0x800) | FOS_NOCHANGEDIR (0x8)
                    uint options = 0x00000020 | 0x00000800 | 0x00000008;
                    dlg.SetOptions(options);
                    dlg.SetTitle("Выбор папки объекта - FERO Launcher");

                    if (!string.IsNullOrEmpty(initialDir)) {
                        try {
                            Guid guid = new Guid("43826d1e-e718-42ee-bc55-a1e261c37bfe");
                            IShellItem folderItem;
                            if (SHCreateItemFromParsingName(initialDir, IntPtr.Zero, ref guid, out folderItem) == 0 && folderItem != null) {
                                dlg.SetFolder(folderItem);
                                Log("Set initialDir: " + initialDir);
                            }
                        } catch (Exception exDir) {
                            Log("Error setting initial dir: " + exDir.Message);
                        }
                    }

                    IntPtr owner = GetForegroundWindow();
                    Log("Showing dialog with owner: " + owner);
                    int hr = dlg.Show(owner);
                    Log("Show returned hr: 0x" + hr.ToString("X8"));

                    if (hr == 0) {
                        IShellItem item = null;
                        try {
                            dlg.GetResult(out item);
                        } catch (Exception exRes) {
                            Log("GetResult threw: " + exRes.Message);
                        }

                        if (item != null) {
                            string path = null;
                            // 1. Try SIGDN_FILESYSPATH (0x80058000)
                            IntPtr pStr = IntPtr.Zero;
                            int hrName = item.GetDisplayName(0x80058000, out pStr);
                            if (hrName == 0 && pStr != IntPtr.Zero) {
                                path = Marshal.PtrToStringUni(pStr);
                                Marshal.FreeCoTaskMem(pStr);
                                Log("Resolved via SIGDN_FILESYSPATH: " + path);
                            }

                            // 2. Fallback to SIGDN_DESKTOPABSOLUTEPARSING (0x80028000) for Google Drive / network drives
                            if (string.IsNullOrEmpty(path)) {
                                pStr = IntPtr.Zero;
                                hrName = item.GetDisplayName(0x80028000, out pStr);
                                if (hrName == 0 && pStr != IntPtr.Zero) {
                                    path = Marshal.PtrToStringUni(pStr);
                                    Marshal.FreeCoTaskMem(pStr);
                                    Log("Resolved via SIGDN_DESKTOPABSOLUTEPARSING: " + path);
                                }
                            }

                            // 3. Fallback to SIGDN_NORMALDISPLAY (0x00000000)
                            if (string.IsNullOrEmpty(path)) {
                                pStr = IntPtr.Zero;
                                hrName = item.GetDisplayName(0x00000000, out pStr);
                                if (hrName == 0 && pStr != IntPtr.Zero) {
                                    path = Marshal.PtrToStringUni(pStr);
                                    Marshal.FreeCoTaskMem(pStr);
                                    Log("Resolved via SIGDN_NORMALDISPLAY: " + path);
                                }
                            }

                            if (!string.IsNullOrEmpty(path)) {
                                // Write to stdout via raw stream (safe for winexe)
                                try {
                                    using (var stdout = Console.OpenStandardOutput()) {
                                        byte[] bytes = new UTF8Encoding(false).GetBytes(path + "\r\n");
                                        stdout.Write(bytes, 0, bytes.Length);
                                        stdout.Flush();
                                    }
                                } catch (Exception exOut) {
                                    Log("OpenStandardOutput failed: " + exOut.Message);
                                    try { Console.WriteLine(path); } catch { }
                                }

                                // Write to out-file if requested
                                if (!string.IsNullOrEmpty(outFile)) {
                                    try {
                                        File.WriteAllText(outFile, path, new UTF8Encoding(false));
                                        Log("Wrote path to outFile: " + outFile);
                                    } catch (Exception exFile) {
                                        Log("Failed to write outFile: " + exFile.Message);
                                    }
                                }

                                Log("SUCCESS returning folder: " + path);
                                return 0;
                            } else {
                                Log("Failed to resolve folder path string.");
                                return 2;
                            }
                        } else {
                            Log("item is null after GetResult");
                            return 2;
                        }
                    }

                    Log("Dialog cancelled by user.");
                    return 1;
                } finally {
                    Marshal.ReleaseComObject(dlg);
                }
            } catch (Exception ex) {
                Log("Fatal exception: " + ex);
                return 2;
            }
        }
    }
}
