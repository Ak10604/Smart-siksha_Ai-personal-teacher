from diffusers import StableDiffusionPipeline
import torch

def main():
    print("🚀 Loading Stable Diffusion v1.5 pipeline...")
    pipe = StableDiffusionPipeline.from_pretrained(
        "runwayml/stable-diffusion-v1-5",
        torch_dtype=torch.float16
    )

    # ✅ Use GPU if available
    if torch.cuda.is_available():
        pipe.to("cuda")
        print("✅ Running on GPU")
    else:
        print("⚠️ Running on CPU (very slow)")

    # Prompt
    prompt = "a robot teaching maths on a white board to a bunch of kids in  classroom"
    negative_prompt = "low quality, blurry, deformed"

    print("🎨 Starting image generation...")
    image = pipe(
        prompt=prompt,
        negative_prompt=negative_prompt,
        num_inference_steps=20,   # fewer steps = faster
        guidance_scale=7.5,       # default scale for SD1.5
        width=512,
        height=512
    ).images[0]

    output_path = "sd15_output.png"
    image.save(output_path)
    print(f"✅ Image saved as {output_path}")

if __name__ == "__main__":
    main()
