import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0c1b2a",
        ocean: "#0c4a6e",
        mist: "#e8f4f8",
      },
    },
  },
  plugins: [],
};

export default config;
