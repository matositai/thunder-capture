import os
import matplotlib
matplotlib.use('Agg') # Use a non-interactive backend to run on systems without a display
import matplotlib.pyplot as plt
from scipy.io import wavfile

def generate_waveform_image(wav_path, output_path, width_px=600, height_px=120, dpi=100):
    """
    Generates a waveform image from a .wav file.
    Handles a dummy file for simulation purposes.
    """
    if not os.path.exists(wav_path):
        print(f"Error: WAV file not found at {wav_path}")
        return False
        
    # --- Simulation Handling ---
    try:
        with open(wav_path, 'r') as f:
            if f.read(5) == 'dummy':
                print("SIMULATION: Detected dummy WAV file. Generating placeholder image.")
                # Create a placeholder image
                fig_width_inches = width_px / dpi
                fig_height_inches = height_px / dpi
                fig, ax = plt.subplots(figsize=(fig_width_inches, fig_height_inches))
                ax.text(0.5, 0.5, 'Simulated Waveform', ha='center', va='center', fontsize=10, color='gray')
                ax.axis('off')
                fig.patch.set_alpha(0)
                ax.patch.set_alpha(0)
                
                output_dir = os.path.dirname(output_path)
                if not os.path.exists(output_dir):
                    os.makedirs(output_dir)
                
                fig.savefig(output_path, dpi=dpi, format='png', transparent=True, pad_inches=0)
                plt.close(fig)
                return True
    except Exception:
        # This will fail on a real binary wav file, which is expected.
        pass

    # --- Real File Processing ---
    try:
        samplerate, data = wavfile.read(wav_path)
        
        if data.ndim > 1:
            data = data[:, 0]
            
        fig_width_inches = width_px / dpi
        fig_height_inches = height_px / dpi
        fig, ax = plt.subplots(figsize=(fig_width_inches, fig_height_inches))
        
        ax.plot(data, color='#007bff', linewidth=0.5)
        
        ax.axis('off')
        fig.patch.set_alpha(0)
        ax.patch.set_alpha(0)
        ax.set_xlim(0, len(data))
        ax.set_ylim(data.min(), data.max())
        plt.tight_layout(pad=0)
        
        output_dir = os.path.dirname(output_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        fig.savefig(output_path, dpi=dpi, format='png', transparent=True, pad_inches=0)
        plt.close(fig)
        
        print(f"Waveform image generated at {output_path}")
        return True

    except Exception as e:
        print(f"Error generating waveform for {wav_path}: {e}")
        return False