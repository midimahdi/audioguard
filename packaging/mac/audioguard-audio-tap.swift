import Foundation
import ScreenCaptureKit
import CoreMedia
import AVFoundation

signal(SIGPIPE, SIG_IGN)

if CommandLine.arguments.contains("--check-permission") {
    let sema = DispatchSemaphore(value: 0)
    var granted = false
    SCShareableContent.getExcludingDesktopWindows(false, onScreenWindowsOnly: true) { content, error in
        if error == nil && content != nil && !(content!.displays.isEmpty) {
            granted = true
        }
        sema.signal()
    }
    _ = sema.wait(timeout: .now() + 2.0)
    exit(granted ? 0 : 1)
}

final class AudioRingBuffer: @unchecked Sendable {
    private var buffer = [Float](repeating: 0, count: 48000 * 4) // 2 second buffer
    private var readIndex = 0
    private var writeIndex = 0
    private var count = 0
    private let lock = NSLock()

    func write(_ data: UnsafePointer<Float>, sampleCount: Int) {
        lock.lock()
        defer { lock.unlock() }
        
        let capacity = buffer.count
        for i in 0..<sampleCount {
            if count == capacity {
                readIndex = (readIndex + 2) % capacity
                count -= 2
            }
            buffer[writeIndex] = data[i]
            writeIndex = (writeIndex + 1) % capacity
            count += 1
        }
    }

    func read(into output: inout [Float], sampleCount: Int) {
        lock.lock()
        defer { lock.unlock() }
        
        let capacity = buffer.count
        let available = min(count, sampleCount)
        
        for i in 0..<available {
            output[i] = buffer[readIndex]
            readIndex = (readIndex + 1) % capacity
            count -= 1
        }
        
        if available < sampleCount {
            for i in available..<sampleCount {
                output[i] = 0.0
            }
        }
    }
}

let ringBuffer = AudioRingBuffer()

class AudioStreamHandler: NSObject, SCStreamOutput, SCStreamDelegate {
    var interleaveBuffer = [Float](repeating: 0, count: 8192)

    func stream(_ stream: SCStream, didOutputSampleBuffer sampleBuffer: CMSampleBuffer, of type: SCStreamOutputType) {
        guard type == .audio else { return }
        let numSamples = Int(CMSampleBufferGetNumSamples(sampleBuffer))
        guard numSamples > 0 else { return }
        guard let desc = CMSampleBufferGetFormatDescription(sampleBuffer) else { return }
        
        let format = AVAudioFormat(cmAudioFormatDescription: desc)
        guard let pcmBuffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: AVAudioFrameCount(numSamples)) else { return }
        pcmBuffer.frameLength = AVAudioFrameCount(numSamples)
        
        let status = CMSampleBufferCopyPCMDataIntoAudioBufferList(
            sampleBuffer,
            at: 0,
            frameCount: Int32(numSamples),
            into: pcmBuffer.mutableAudioBufferList
        )
        guard status == noErr, let channelData = pcmBuffer.floatChannelData else { return }
        let left = channelData[0]
        let right = (format.channelCount > 1) ? channelData[1] : channelData[0]
        
        let totalFloats = numSamples * 2
        if interleaveBuffer.count < totalFloats {
            interleaveBuffer = [Float](repeating: 0, count: totalFloats)
        }
        
        for i in 0..<numSamples {
            interleaveBuffer[i * 2] = left[i]
            interleaveBuffer[i * 2 + 1] = right[i]
        }
        
        interleaveBuffer.withUnsafeBufferPointer { ptr in
            if let base = ptr.baseAddress {
                ringBuffer.write(base, sampleCount: totalFloats)
            }
        }
    }

    func stream(_ stream: SCStream, didStopWithError error: Error) {
        fputs("Audio stream error: \(error.localizedDescription)\n", stderr)
        exit(1)
    }
}

let handler = AudioStreamHandler()
var keepAliveStream: SCStream?

// Timer writes continuous 10ms audio blocks (480 frames = 960 floats)
let tickFrames = 480
let tickFloats = tickFrames * 2
var tickBuffer = [Float](repeating: 0, count: tickFloats)
let byteCount = tickFloats * MemoryLayout<Float>.size

let timer = DispatchSource.makeTimerSource(flags: .strict, queue: DispatchQueue.global(qos: .userInteractive))
timer.schedule(deadline: .now(), repeating: .milliseconds(10), leeway: .microseconds(500))
timer.setEventHandler {
    ringBuffer.read(into: &tickBuffer, sampleCount: tickFloats)
    let written = tickBuffer.withUnsafeBytes { rawPtr in
        write(STDOUT_FILENO, rawPtr.baseAddress, byteCount)
    }
    if written < 0 {
        exit(0)
    }
}
timer.resume()

// Signals
let termSource = DispatchSource.makeSignalSource(signal: SIGTERM, queue: .main)
termSource.setEventHandler { exit(0) }
termSource.resume()

let intSource = DispatchSource.makeSignalSource(signal: SIGINT, queue: .main)
intSource.setEventHandler { exit(0) }
intSource.resume()

Task {
    do {
        let content = try await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: true)
        guard let display = content.displays.first else {
            fputs("Error: No display found\n", stderr)
            exit(1)
        }
        
        let filter = SCContentFilter(display: display, excludingApplications: [], exceptingWindows: [])
        let config = SCStreamConfiguration()
        config.capturesAudio = true
        config.sampleRate = 48000
        config.channelCount = 2
        config.excludesCurrentProcessAudio = false
        config.width = 64
        config.height = 64
        config.minimumFrameInterval = CMTime(value: 1, timescale: 10)
        
        let stream = SCStream(filter: filter, configuration: config, delegate: handler)
        keepAliveStream = stream
        let queue = DispatchQueue(label: "sc.audio.queue", qos: .userInteractive)
        try stream.addStreamOutput(handler, type: .screen, sampleHandlerQueue: queue)
        try stream.addStreamOutput(handler, type: .audio, sampleHandlerQueue: queue)
        try await stream.startCapture()
        fputs("ScreenCaptureKit audio stream active\n", stderr)
    } catch {
        fputs("Error starting ScreenCaptureKit: \(error.localizedDescription)\n", stderr)
        exit(1)
    }
}

RunLoop.main.run()
