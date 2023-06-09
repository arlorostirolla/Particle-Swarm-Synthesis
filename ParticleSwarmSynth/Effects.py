import numpy as np
import librosa
from scipy import signal
from scipy.signal import butter, lfilter
import soundfile as sf
import itertools
import random
from functools import partial
from scipy.io import wavfile

oscillator_types = ['sine', 'square', 'sawtooth', 'triangle', 'pwm', 'noise', 'sine2', 'sawtooth2', 'triangle2', 'harmonic', 'sawtooth3', 'triangle3', 'square3', 'fm_sine', 'fm_square', 'fm_sawtooth', 'fm_triangle']


def analyze_wav(file_path):
    # Load the .wav file
    sample_rate, audio_data = wavfile.read(file_path)

    # Convert stereo audio to mono if necessary
    if len(audio_data.shape) > 1 and audio_data.shape[1] > 1:
        audio_data = audio_data.mean(axis=1)

    # Calculate the duration of the audio in seconds
    duration = len(audio_data) / sample_rate

    # Estimate the pitch using librosa
    pitches, magnitudes = librosa.piptrack(y=audio_data.astype(np.float32), sr=sample_rate)
    index = magnitudes.argmax()
    pitch = pitches[index // pitches.shape[0], index % pitches.shape[1]]

    return pitch, duration, sample_rate

def pwm_wave(freq, length, sr, duty_cycle=0.5):
    t = np.linspace(0, length, int(length * sr), endpoint=False)
    return signal.square(2 * np.pi * freq * t, duty=duty_cycle)

def white_noise(length, sr):
    return np.random.uniform(-1, 1, size=int(length * sr))

def normalize_audio(audio):
    return audio / np.max(np.abs(audio))

def oscillator(freq, length, sr, osc_type='sine', fm_index=0, fm_freq=0):
    t = np.linspace(0, length, int(length * sr), endpoint=False)
   
    if osc_type == 'sine':
        return np.sin(2 * np.pi * freq * t)
    elif osc_type == 'square':
        return signal.square(2 * np.pi * freq * t)
    elif osc_type == 'sawtooth':
        return signal.sawtooth(2 * np.pi * freq * t)
    elif osc_type == 'triangle':
        return signal.sawtooth(2 * np.pi * freq * t, 0.5)
    elif osc_type == 'pwm':
        return pwm_wave(freq, length, sr)
    elif osc_type == 'noise':
        return white_noise(length, sr)
    elif osc_type == 'sine2':
        return np.sin(2 * np.pi * freq * t) + np.sin(2 * np.pi * 2 * freq * t) / 2
    elif osc_type == 'sawtooth2':
        return signal.sawtooth(2 * np.pi * freq * t) + signal.sawtooth(2 * np.pi * 2 * freq * t) / 2
    elif osc_type == 'triangle2':
        return signal.sawtooth(2 * np.pi * freq * t, 0.5) + signal.sawtooth(2 * np.pi * 2 * freq * t, 0.5) / 2
    elif osc_type == 'harmonic':
        return np.sin(2 * np.pi * freq * t) + np.sin(2 * np.pi * 2 * freq * t) / 2 + np.sin(2 * np.pi * 3 * freq * t) / 3
    elif osc_type == 'sawtooth3':
        return signal.sawtooth(2 * np.pi * freq * t) + signal.sawtooth(2 * np.pi * 2 * freq * t) / 2 + signal.sawtooth(2 * np.pi * 3 * freq * t) / 3
    elif osc_type == 'triangle3':
        return signal.sawtooth(2 * np.pi * freq * t, 0.5) + signal.sawtooth(2 * np.pi * 2 * freq * t, 0.5) / 2 + signal.sawtooth(2 * np.pi * 3 * freq * t, 0.5) / 3
    elif osc_type == 'square3':
        return signal.square(2 * np.pi * freq * t) + signal.square(2 * np.pi * 2 * freq * t) / 2 + signal.square(2 * np.pi * 3 * freq * t) / 3
    elif osc_type == 'fm_sine':
        carrier = np.sin(2 * np.pi * freq * t)
        modulator = np.sin(2 * np.pi * fm_freq * t)
        return np.sin(2 * np.pi * (freq + fm_index * modulator) * t)
    elif osc_type == 'fm_square':
        carrier = signal.square(2 * np.pi * freq * t)
        modulator = signal.square(2 * np.pi * fm_freq * t)
        return signal.square(2 * np.pi * (freq + fm_index * modulator) *t)
    elif osc_type == 'fm_sawtooth':
        carrier = signal.sawtooth(2 * np.pi * freq * t)
        modulator = signal.sawtooth(2 * np.pi * fm_freq * t)
        return signal.sawtooth(2 * np.pi * (freq + fm_index * modulator) * t)
    elif osc_type == 'fm_triangle':
        carrier = signal.sawtooth(2 * np.pi * freq * t, 0.5)
        modulator = signal.sawtooth(2 * np.pi * fm_freq * t, 0.5)
        return signal.sawtooth(2 * np.pi * (freq + fm_index * modulator) * t, 0.5)
    else:
        raise ValueError(f"Invalid oscillator type '{osc_type}'")

def adsr_envelope(audio, length, sr, attack, decay, sustain, release, on):
    if on:
        total_samples = len(audio)
        max_attack_samples = int(np.round(length * sr / 4))
        max_decay_samples = int(np.round(length * sr / 4))
        attack_samples = int(np.round(attack * sr))
        decay_samples = int(np.round(decay * sr))
        release_samples = int(np.round(release * sr))
        sustain_samples = total_samples - attack_samples - decay_samples - release_samples

        # Ensure attack and decay times are within acceptable range
        attack_samples = min(attack_samples, max_attack_samples)
        decay_samples = min(decay_samples, max_decay_samples)

        envelope = np.zeros(total_samples)

        # Attack phase
        attack_values = np.linspace(0, 1, attack_samples, endpoint=False)
        envelope[:attack_samples] = attack_values

        # Decay phase
        decay_values = np.linspace(1, sustain, decay_samples, endpoint=False)
        envelope[attack_samples:attack_samples + decay_samples] = decay_values

        # Sustain phase
        envelope[attack_samples + decay_samples:total_samples - release_samples] = sustain

        # Release phase
        release_values = np.linspace(sustain, 0, release_samples, endpoint=True)
        envelope[-release_samples:] = release_values

        # Apply the envelope to the audio
        modified_audio = audio * envelope

        return modified_audio
    else:
        return audio

def filter_envelope(audio, length, sr, freq_cutoff, freq_start, freq_end, on):
    if on:
        total_samples = len(audio)
        envelope = np.linspace(freq_start, freq_end, total_samples)
        b, a = signal.butter(2, freq_cutoff / (sr / 2), btype='low', analog=False, output='ba')

        # Generate the filter
        filtered_envelope = signal.lfilter(b, a, envelope)

        # Normalize the filtered envelope
        filtered_envelope /= np.max(np.abs(filtered_envelope), axis=0)

        # Apply the filter to the audio
        modified_audio = audio * filtered_envelope

        return modified_audio
    else:
        return audio


def lowpass_filter(audio, cutoff, resonance, sr, on):
    if on:
        nyq = 0.5 * sr
        normalized_cutoff = cutoff / nyq
        b, a = butter(2, normalized_cutoff, btype='low', analog=False, output='ba')
        filtered_audio = lfilter(b, a, audio)
        return filtered_audio * resonance
    else:
        return audio

def highpass_filter(audio, cutoff, resonance, sr, on):
    if on:
        nyq = 0.5 * sr
        normalized_cutoff = cutoff / nyq
        b, a = butter(2, normalized_cutoff, btype='high', analog=False, output='ba')
        filtered_audio = lfilter(b, a, audio)
        return filtered_audio * resonance
    else:
        return audio

def compressor(audio, threshold, ratio, attack, release, on):
    if on:    
        # Apply compressor effect
        rms = np.sqrt(np.mean(audio**2))
        if rms > threshold:
            env = adsr_envelope(len(audio), 44100, attack, 0, 1, release)
            gain_reduction = (rms - threshold) / (rms * ratio - threshold + np.finfo(float).eps)
            audio = audio * (1 - env * gain_reduction)
        return audio 
    else:
        return audio

def reverb(audio, sr, delay, decay, on):
    # Apply reverb effect using a feedback delay network
    # The delay parameter should be in seconds, and decay should be a value between 0 and 1
    # We'll use a simple 3-tap delay line with equal feedback
    if on:
        # Convert delay from seconds to samples
        delay_samples = int(delay * sr)
        # Initialize delay buffer with zeros
        buffer = np.zeros(delay_samples + len(audio))
        # Apply delay and feedback
        for i in range(len(audio)):
            # Output the delayed signal
            delayed = buffer[i] * decay
            # Add input to delay buffer
            buffer[i + delay_samples] += audio[i]
            # Add output to delay buffer
            buffer[i] += delayed
            # Mix delayed and input signals
            audio[i] = audio[i] + delayed
        return audio
    else:
        return audio

def distortion(audio, threshold, on):
    # Apply distortion effect using soft clipping
    # The threshold parameter should be a value between 0 and 1
    # Apply soft clipping function
    
    if on:
        audio = np.tanh(audio / threshold) * threshold
        return audio
    else:
        return audio

def equalizer(audio, sr, eq_params, on):
    if on:
        biquads = []
        for i in range(len(eq_params) // 3):
            center_freq = eq_params[i * 3]
            gain = eq_params[i * 3 + 1]
            q = eq_params[i * 3 + 2]

            # Calculate biquad coefficients
            w0 = 2 * np.pi * center_freq / sr
            alpha = np.sin(w0) / (2 * q)
            A = 10**(gain / 40)
            if gain >= 0:
                b0 = (1 + alpha * A)
                b1 = (-2 * np.cos(w0))
                b2 = (1 - alpha * A)
                a0 = (1 + alpha / A)
                a1 = (-2 * np.cos(w0))
                a2 = (1 - alpha / A)
            else:
                b0 = (1 - alpha / A)
                b1 = (-2 * np.cos(w0))
                b2 = (1 + alpha / A)
                a0 = (1 + alpha * A)
                a1 = (-2 * np.cos(w0))
                a2 = (1 - alpha * A)

            b = np.array([b0, b1, b2])
            a = np.array([a0, a1, a2])
            biquads.append((b, a))

        # Apply biquad filters to the audio signal
        filtered_audio = audio.copy()
        for b, a in biquads:
            filtered_audio = lfilter(b, a, filtered_audio)

        return filtered_audio
    else:
        return audio

def generate_wavetables(harmonic_amplitudes, num_harmonics, num_wavetables, wavetable_size):
    wavetables = []

    for i in range(num_wavetables):
        wavetable = np.zeros(wavetable_size)
        harmonics = np.random.uniform(0, 1, num_harmonics) * harmonic_amplitudes

        for h in range(1, num_harmonics + 1):
            harmonic_wave = harmonics[h - 1] * np.sin(2 * np.pi * h * np.arange(wavetable_size) / wavetable_size)
            wavetable += harmonic_wave

        # Normalize the wavetable
        wavetable /= np.max(np.abs(wavetable))

        wavetables.append(wavetable)

    return wavetables
