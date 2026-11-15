using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;
using System.Reflection;

[assembly: AssemblyTitle("MOZKAN Live Sub")]
[assembly: AssemblyProduct("MOZKAN Live Sub")]
[assembly: AssemblyCompany("MOZKAN")]
[assembly: AssemblyDescription("Yerel ekran altyazısı çevirisi")]

internal static class Launcher
{
    [STAThread]
    private static int Main(string[] args)
    {
        string root = AppDomain.CurrentDomain.BaseDirectory;
        string runtime = Path.Combine(root, "python", "pythonw.exe");
        string models = Path.Combine(root, "models");
        string data = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "AltyaziAtolyesi");
        string logPath = Path.Combine(data, "startup.log");
        try
        {
            Directory.CreateDirectory(data);
            if (!File.Exists(runtime)) throw new FileNotFoundException("Python ortamı bulunamadı.", runtime);
            if (!Directory.Exists(models)) throw new DirectoryNotFoundException("Yerel model klasörü bulunamadı: " + models);
            using (var log = new StreamWriter(logPath, true))
            using (var process = new Process())
            {
                log.AutoFlush = true;
                log.WriteLine("\n--- " + DateTime.Now.ToString("s") + " ---");
                var info = new ProcessStartInfo(runtime);
                info.Arguments = "-E -s -X utf8 \"" + Path.Combine(root, "src", "main.py") + "\" --models \"" + models + "\"";
                if (args.Length == 1 && args[0] == "--self-test") info.Arguments += " --self-test";
                info.WorkingDirectory = root;
                info.UseShellExecute = false;
                info.CreateNoWindow = true;
                info.RedirectStandardOutput = true;
                info.RedirectStandardError = true;
                process.StartInfo = info;
                DataReceivedEventHandler write = (sender, e) => { if (e.Data != null) lock(log) log.WriteLine(e.Data); };
                process.OutputDataReceived += write;
                process.ErrorDataReceived += write;
                process.Start();
                process.BeginOutputReadLine();
                process.BeginErrorReadLine();
                process.WaitForExit();
                if (process.ExitCode != 0) MessageBox.Show("Uygulama kapandı. Günlük: " + logPath, "MOZKAN Live Sub", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return process.ExitCode;
            }
        }
        catch (Exception error)
        {
            MessageBox.Show(error.Message + "\nGünlük: " + logPath, "MOZKAN Live Sub", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
