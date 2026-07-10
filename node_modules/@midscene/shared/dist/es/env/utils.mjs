import { GlobalConfigManager } from "./global-config-manager.mjs";
import { ModelConfigManager } from "./model-config-manager.mjs";
import { MIDSCENE_PREFERRED_LANGUAGE } from "./types.mjs";
const globalModelConfigManager = new ModelConfigManager();
const globalConfigManager = new GlobalConfigManager();
globalConfigManager.registerModelConfigManager(globalModelConfigManager);
globalModelConfigManager.registerGlobalConfigManager(globalConfigManager);
const getPreferredLanguage = ()=>{
    const prefer = globalConfigManager.getEnvConfigValue(MIDSCENE_PREFERRED_LANGUAGE);
    if (prefer) return prefer;
    const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    const isChina = 'Asia/Shanghai' === timeZone;
    return isChina ? 'Chinese' : 'English';
};
const overrideAIConfig = (newConfig, extendMode = false)=>{
    globalConfigManager.overrideAIConfig(newConfig, extendMode);
};
export { getPreferredLanguage, globalConfigManager, globalModelConfigManager, overrideAIConfig };
