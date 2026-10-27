import { resolve } from "path";
import config from "./nuxt.config";

export default {
  ...config,
  buildDir: ".nuxt-deploy",
  typescript: {
    typeCheck: {
      typescript: {
        configFile: resolve(__dirname, "tsconfig.production.json"),
        extensions: { vue: true },
      },
    },
  },
};
