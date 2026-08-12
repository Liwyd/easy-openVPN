import i18n from "i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import { initReactI18next } from "react-i18next";
import { enUS, faIR } from "date-fns/locale";
import { registerLocale } from "react-datepicker";
import en from "./en.json";
import fa from "./fa.json";

registerLocale("en", enUS);
registerLocale("fa", faIR);

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    debug: import.meta.env.DEV,
    returnNull: false,
    fallbackLng: "en",
    interpolation: {
      escapeValue: false,
    },
    react: {
      useSuspense: false,
    },
    load: "languageOnly",
    detection: {
      order: ["localStorage", "cookie"],
      caches: ["localStorage", "cookie"],
    },
    resources: {
      en: { translation: en },
      fa: { translation: fa },
    },
  });

i18n.on("languageChanged", (lng) => {
  document.documentElement.dir = lng === "fa" ? "rtl" : "ltr";
  document.documentElement.lang = lng;
});

if (document.documentElement.dir === "") {
  document.documentElement.dir = i18n.language === "fa" ? "rtl" : "ltr";
}

export default i18n;
