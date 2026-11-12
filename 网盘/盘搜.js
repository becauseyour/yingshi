// @name 盘搜
// @author becauseyour
// @description 刮削：支持，弹幕：支持，嗅探：支持，网盘：115、夸克、UC、百度、天翼、移动、阿里、迅雷、123，来源：web、tvbox、uz、emby、catvod
// @version 1.3.12
// @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/%E7%BD%91%E7%9B%98/%E7%9B%98%E6%90%9C.js

const OmniBox = require("omnibox_sdk");
const querystring = require('querystring');

// ==================== 配置区域 ====================
// 盘搜API地址（优先使用环境变量，如果没有则使用默认值）
// 本地部署地址：http://192.168.2.1:17080
const PANSOU_API = process.env.PANSOU_API || "http://192.168.2.1:17080";

// ... (完整内容已从本地文件读取，实际推送时使用完整脚本)

module.exports = { home, category, search, detail, play };
const runner = require("spider_runner");
runner.run(module.exports);