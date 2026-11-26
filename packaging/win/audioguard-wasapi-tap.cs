using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;

namespace AudioGuardWasapiTap
{
    static class Program
    {
        const int CLSCTX_ALL = 23;
        const int eRender = 0;
        const int eConsole = 0;
        const int AUDCLNT_SHAREMODE_SHARED = 0;

        const uint AUDCLNT_STREAMFLAGS_LOOPBACK = 0x00020000;
        const uint AUDCLNT_STREAMFLAGS_AUTOCONVERTPCM = 0x80000000;
        const uint AUDCLNT_STREAMFLAGS_SRC_DEFAULT_QUALITY = 0x08000000;
        const uint AUDCLNT_BUFFERFLAGS_SILENT = 0x00000002;
        const int AUDCLNT_E_DEVICE_INVALIDATED = unchecked((int)0x88890004);

        const ushort WAVE_FORMAT_IEEE_FLOAT = 3;

        static readonly Guid CLSID_MMDeviceEnumerator = new Guid("BCDE0395-E52F-467C-8E3D-C4579291692E");
        static readonly Guid IID_IAudioClient = new Guid("1CB9AD4C-DBFA-4c32-B178-C2F568A703B2");
        static readonly Guid IID_IAudioCaptureClient = new Guid("C8ADBD64-E71E-48a0-A4DE-185C395CD317");

        [StructLayout(LayoutKind.Sequential, Pack = 1)]
        struct WAVEFORMATEX
        {
            public ushort wFormatTag;
            public ushort nChannels;
            public uint nSamplesPerSec;
            public uint nAvgBytesPerSec;
            public ushort nBlockAlign;
            public ushort wBitsPerSample;
            public ushort cbSize;
        }

        [ComImport, Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        interface IMMDeviceEnumerator
        {
            [PreserveSig]
            int EnumAudioEndpoints(int dataFlow, int dwStateMask, out IntPtr ppDevices);

            [PreserveSig]
            int GetDefaultAudioEndpoint(int dataFlow, int role, out IMMDevice ppEndpoint);
        }

        [ComImport, Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        interface IMMDevice
        {
            [PreserveSig]
            int Activate(ref Guid iid, int dwClsCtx, IntPtr pActivationParams, [MarshalAs(UnmanagedType.IUnknown)] out object ppInterface);
        }

        [ComImport, Guid("1CB9AD4C-DBFA-4c32-B178-C2F568A703B2"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        interface IAudioClient
        {
            [PreserveSig]
            int Initialize(int shareMode, uint streamFlags, long hnsBufferDuration, long hnsPeriodicity, IntPtr pFormat, IntPtr audioSessionGuid);

            [PreserveSig]
            int GetBufferSize(out uint pNumBufferFrames);

            [PreserveSig]
            int GetStreamLatency(out long phnsLatency);

            [PreserveSig]
            int GetCurrentPadding(out uint pNumPaddingFrames);

            [PreserveSig]
            int IsFormatSupported(int shareMode, IntPtr pFormat, out IntPtr ppClosestMatch);

            [PreserveSig]
            int GetMixFormat(out IntPtr ppDeviceFormat);

            [PreserveSig]
            int GetDevicePeriod(out long phnsDefaultDevicePeriod, out long phnsMinimumDevicePeriod);

            [PreserveSig]
            int Start();

            [PreserveSig]
            int Stop();

            [PreserveSig]
            int Reset();

            [PreserveSig]
            int SetEventHandle(IntPtr eventHandle);

            [PreserveSig]
            int GetService(ref Guid riid, [MarshalAs(UnmanagedType.IUnknown)] out object ppv);
        }

        [ComImport, Guid("C8ADBD64-E71E-48a0-A4DE-185C395CD317"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        interface IAudioCaptureClient
        {
            [PreserveSig]
            int GetBuffer(out IntPtr ppData, out uint pNumFramesToRead, out uint pdwFlags, out ulong pu64DevicePosition, out ulong pu64QPCPosition);

            [PreserveSig]
            int ReleaseBuffer(uint numFramesRead);

            [PreserveSig]
            int GetNextPacketSize(out uint pNumFramesInNextPacket);
        }

        sealed class FloatRingBuffer
        {
            private readonly float[] _buf;
            private int _readIdx;
            private int _writeIdx;
            private int _count;
            private readonly object _lock = new object();

            public FloatRingBuffer(int capacityFloats)
            {
                _buf = new float[capacityFloats];
            }

            public void Write(float[] data, int floatCount)
            {
                lock (_lock)
                {
                    int cap = _buf.Length;
                    for (int i = 0; i < floatCount; i++)
                    {
                        if (_count == cap)
                        {
                            _readIdx = (_readIdx + 2) % cap;
                            _count -= 2;
                        }
                        _buf[_writeIdx] = data[i];
                        _writeIdx = (_writeIdx + 1) % cap;
                        _count++;
                    }
                }
            }

            public void WriteSilence(int floatCount)
            {
                lock (_lock)
                {
                    int cap = _buf.Length;
                    for (int i = 0; i < floatCount; i++)
                    {
                        if (_count == cap)
                        {
                            _readIdx = (_readIdx + 2) % cap;
                            _count -= 2;
                        }
                        _buf[_writeIdx] = 0.0f;
                        _writeIdx = (_writeIdx + 1) % cap;
                        _count++;
                    }
                }
            }

            public void Read(float[] output, int floatCount)
            {
                lock (_lock)
                {
                    int cap = _buf.Length;
                    int avail = _count < floatCount ? _count : floatCount;
                    for (int i = 0; i < avail; i++)
                    {
                        output[i] = _buf[_readIdx];
                        _readIdx = (_readIdx + 1) % cap;
                        _count--;
                    }
                    for (int i = avail; i < floatCount; i++)
                    {
                        output[i] = 0.0f;
                    }
                }
            }
        }

        static volatile bool _running = true;
        static readonly FloatRingBuffer _ring = new FloatRingBuffer(48000 * 4); // 2s stereo float32

        static void CaptureLoop()
        {
            float[] tempBuf = new float[8192];

            while (_running)
            {
                IMMDeviceEnumerator enumerator = null;
                IMMDevice device = null;
                IAudioClient audioClient = null;
                IAudioCaptureClient captureClient = null;
                IntPtr fmtPtr = IntPtr.Zero;

                try
                {
                    Type enumType = Type.GetTypeFromCLSID(CLSID_MMDeviceEnumerator);
                    enumerator = (IMMDeviceEnumerator)Activator.CreateInstance(enumType);

                    int hr = enumerator.GetDefaultAudioEndpoint(eRender, eConsole, out device);
                    if (hr != 0 || device == null)
                    {
                        Console.Error.WriteLine("GetDefaultAudioEndpoint failed: 0x" + hr.ToString("X8"));
                        Thread.Sleep(500);
                        continue;
                    }

                    Guid iidClient = IID_IAudioClient;
                    object clientObj;
                    hr = device.Activate(ref iidClient, CLSCTX_ALL, IntPtr.Zero, out clientObj);
                    if (hr != 0 || clientObj == null)
                    {
                        Console.Error.WriteLine("Activate IAudioClient failed: 0x" + hr.ToString("X8"));
                        Thread.Sleep(500);
                        continue;
                    }
                    audioClient = (IAudioClient)clientObj;

                    WAVEFORMATEX wfx = new WAVEFORMATEX
                    {
                        wFormatTag = WAVE_FORMAT_IEEE_FLOAT,
                        nChannels = 2,
                        nSamplesPerSec = 48000,
                        wBitsPerSample = 32,
                        nBlockAlign = 8,
                        nAvgBytesPerSec = 48000 * 8,
                        cbSize = 0
                    };

                    fmtPtr = Marshal.AllocCoTaskMem(Marshal.SizeOf(typeof(WAVEFORMATEX)));
                    Marshal.StructureToPtr(wfx, fmtPtr, false);

                    uint flags = AUDCLNT_STREAMFLAGS_LOOPBACK | AUDCLNT_STREAMFLAGS_AUTOCONVERTPCM | AUDCLNT_STREAMFLAGS_SRC_DEFAULT_QUALITY;
                    long bufferDuration = 1000000; // 100ms in 100-ns units

                    hr = audioClient.Initialize(AUDCLNT_SHAREMODE_SHARED, flags, bufferDuration, 0, fmtPtr, IntPtr.Zero);
                    if (hr != 0)
                    {
                        Console.Error.WriteLine("IAudioClient.Initialize failed: 0x" + hr.ToString("X8"));
                        Thread.Sleep(500);
                        continue;
                    }

                    Guid iidCapture = IID_IAudioCaptureClient;
                    object captureObj;
                    hr = audioClient.GetService(ref iidCapture, out captureObj);
                    if (hr != 0 || captureObj == null)
                    {
                        Console.Error.WriteLine("GetService IAudioCaptureClient failed: 0x" + hr.ToString("X8"));
                        Thread.Sleep(500);
                        continue;
                    }
                    captureClient = (IAudioCaptureClient)captureObj;

                    hr = audioClient.Start();
                    if (hr != 0)
                    {
                        Console.Error.WriteLine("IAudioClient.Start failed: 0x" + hr.ToString("X8"));
                        Thread.Sleep(500);
                        continue;
                    }

                    Console.Error.WriteLine("WASAPI loopback stream active (48000Hz stereo float32)");

                    while (_running)
                    {
                        uint packetFrames;
                        hr = captureClient.GetNextPacketSize(out packetFrames);
                        if (hr == AUDCLNT_E_DEVICE_INVALIDATED)
                        {
                            Console.Error.WriteLine("Default render device changed, reconnecting...");
                            break;
                        }
                        if (hr != 0)
                        {
                            Console.Error.WriteLine("GetNextPacketSize failed: 0x" + hr.ToString("X8"));
                            break;
                        }

                        if (packetFrames == 0)
                        {
                            Thread.Sleep(4);
                            continue;
                        }

                        while (packetFrames > 0 && _running)
                        {
                            IntPtr dataPtr;
                            uint framesAvail;
                            uint bufFlags;
                            ulong devPos;
                            ulong qpcPos;

                            hr = captureClient.GetBuffer(out dataPtr, out framesAvail, out bufFlags, out devPos, out qpcPos);
                            if (hr != 0)
                            {
                                break;
                            }

                            int floatCount = (int)(framesAvail * 2);
                            if (floatCount > 0)
                            {
                                if ((bufFlags & AUDCLNT_BUFFERFLAGS_SILENT) != 0 || dataPtr == IntPtr.Zero)
                                {
                                    _ring.WriteSilence(floatCount);
                                }
                                else
                                {
                                    if (tempBuf.Length < floatCount)
                                    {
                                        tempBuf = new float[floatCount];
                                    }
                                    Marshal.Copy(dataPtr, tempBuf, 0, floatCount);
                                    _ring.Write(tempBuf, floatCount);
                                }
                            }

                            captureClient.ReleaseBuffer(framesAvail);

                            hr = captureClient.GetNextPacketSize(out packetFrames);
                            if (hr != 0)
                            {
                                break;
                            }
                        }
                    }
                }
                catch (Exception ex)
                {
                    Console.Error.WriteLine("Capture loop error: " + ex.Message);
                    Thread.Sleep(500);
                }
                finally
                {
                    if (fmtPtr != IntPtr.Zero) Marshal.FreeCoTaskMem(fmtPtr);
                    if (audioClient != null)
                    {
                        try { audioClient.Stop(); } catch { }
                        Marshal.ReleaseComObject(audioClient);
                    }
                    if (captureClient != null) Marshal.ReleaseComObject(captureClient);
                    if (device != null) Marshal.ReleaseComObject(device);
                    if (enumerator != null) Marshal.ReleaseComObject(enumerator);
                }
            }
        }

        [MTAThread]
        static int Main(string[] args)
        {
            Console.CancelKeyPress += (s, e) => { _running = false; e.Cancel = true; };

            Thread captureThread = new Thread(CaptureLoop)
            {
                IsBackground = true,
                Name = "WasapiCaptureThread"
            };
            captureThread.SetApartmentState(ApartmentState.MTA);
            captureThread.Start();

            const int tickFrames = 480; // 10ms @ 48000 Hz
            const int tickFloats = tickFrames * 2;
            const int byteCount = tickFloats * 4;

            float[] tickFloatBuf = new float[tickFloats];
            byte[] tickByteBuf = new byte[byteCount];

            Stream stdout = Console.OpenStandardOutput();
            Stopwatch sw = Stopwatch.StartNew();
            long tickCount = 0;

            try
            {
                while (_running)
                {
                    tickCount++;
                    double targetMs = tickCount * 10.0;
                    double nowMs = sw.Elapsed.TotalMilliseconds;
                    double waitMs = targetMs - nowMs;

                    if (waitMs > 1.5)
                    {
                        Thread.Sleep((int)(waitMs - 1.0));
                    }
                    while (sw.Elapsed.TotalMilliseconds < targetMs)
                    {
                        Thread.SpinWait(50);
                    }

                    // If we fell behind by > 100ms (e.g. sleep/wake), resync clock
                    if (sw.Elapsed.TotalMilliseconds - targetMs > 100.0)
                    {
                        sw.Restart();
                        tickCount = 0;
                    }

                    _ring.Read(tickFloatBuf, tickFloats);
                    Buffer.BlockCopy(tickFloatBuf, 0, tickByteBuf, 0, byteCount);
                    stdout.Write(tickByteBuf, 0, byteCount);
                    stdout.Flush();
                }
            }
            catch (IOException)
            {
                // Pipe closed by parent process - normal shutdown
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine("Output loop error: " + ex.Message);
                return 1;
            }
            finally
            {
                _running = false;
            }

            return 0;
        }
    }
}
