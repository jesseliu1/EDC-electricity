/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useMemo, useRef, useCallback } from 'react';
import {   
  Activity, Package, Database, Terminal, LayoutGrid, X,   
  Download, Sun, Moon, Search, Cpu, Globe, Check,   
  ChevronRight, ChevronDown, Zap, ShieldCheck, Clock,  
  Settings, Key, User, Power, Save, RefreshCw, Smartphone,  
  Info, AlertTriangle, FileText, ChevronLeft, Plus, Sparkles, Wand2, Image as ImageIcon
} from 'lucide-react';  
import { GoogleGenAI } from "@google/genai";
import { toggleWindowState } from './hostConnectivityState';
import HostSettingsView from './SettingsView';
  
/**  
 * ASNS (AI Sensory Nervous System) - 邊緣側作業系統  
 * 核心規範：  
 * 1. 視覺：iOS 白色科技風格 (支援明亮/黑暗模式)  
 * 2. 語系：10 國語言支援 (i18n 引擎)  
 * 3. 架構：L1 (RocksDB) -> L2 (Python/PostgreSQL) -> L3 (OpenClaw/AI)  
 * 4. 命名：Nickname > Name > ID (CUID/SUID)  
 */  
  
// --- 國際化語系定義 (10 國語言) ---  
const translations: Record<string, Record<string, string>> = {  
  'zh-TW': { name: '繁體中文', app: 'ASNS（AI Sensory Nervous System）AI感知神經系統', connect: '連線設置', store: '應用商店', devices: '設備目錄', dash: '實時看板', dev: '開發工具', status: '系統狀態', cpu: '處理器', ram: '記憶體', ssd: '硬碟壽命', online: '在線', offline: '離線', install: '下載應用', l1: '感知層 (RocksDB)', l2: '傳導層 (SQL)', l3: '大腦層 (AI)', sync: '同步清單', nickname: '別名優先', apply: '儲存設定', diagnosis: '診斷報告', rca: '原因分析', capa: '改善措施', pythonApp: 'Python 應用', skill: '技能' },  
  'zh-CN': { name: '简体中文', app: 'ASNS（AI Sensory Nervous System）AI感知神经系统', connect: '连线设置', store: '应用商店', devices: '设备目录', dash: '实时看板', dev: '开发工具', status: '系统状态', cpu: '处理器', ram: '内存', ssd: '硬盘寿命', online: '在线', offline: '离线', install: '下载应用', l1: '感知层 (RocksDB)', l2: '传导层 (SQL)', l3: '大脑层 (AI)', sync: '同步清单', nickname: '别名優先', apply: '保存设置', diagnosis: '诊断报告', rca: '原因分析', capa: '改善措施', pythonApp: 'Python 应用', skill: '技能' },  
  'en-US': { name: 'English', app: 'ASNS (AI Sensory Nervous System)', connect: 'Connectivity', store: 'App Store', devices: 'Sensors', dash: 'Dashboard', dev: 'IDE', status: 'Status', cpu: 'CPU', ram: 'RAM', ssd: 'SSD Life', online: 'Online', offline: 'Offline', install: 'Install', l1: 'Sensory (RocksDB)', l2: 'Transmission (SQL)', l3: 'Cognitive (AI)', sync: 'Sync', nickname: 'Nickname First', apply: 'Apply', diagnosis: 'AI Report', rca: 'RCA', capa: 'CAPA', pythonApp: 'Python App', skill: 'Skill' },  
  'ja-JP': { name: '日本語', app: 'ASNS（AI感覚神経系）', connect: '接続設定', store: 'ストア', devices: 'デバイス', dash: 'パネル', dev: 'ツール', status: 'ステータス', cpu: 'CPU', ram: 'メモリ', ssd: 'SSD寿命', online: 'オンライン', offline: 'オフライン', install: '導入', l1: '感知層', l2: '伝導層', l3: '知能層', sync: '同期', nickname: '別名優先', apply: '適用', diagnosis: '診断報告', rca: '原因分析', capa: '改善策', pythonApp: 'Python アプリ', skill: 'スキル' },  
  'ko-KR': { name: '한국어', app: 'ASNS（AI 감각 신경계）', connect: '연결 설정', store: '스토어', devices: '장치', dash: '대시보드', dev: '도구', status: '상태', cpu: 'CPU', ram: 'RAM', ssd: 'SSD 수명', online: '온라인', offline: '오프라인', install: '설치', l1: '감지층', l2: '전송층', l3: '지능층', sync: '동기화', nickname: '별칭 우선', apply: '적용', diagnosis: '진단 보고서', rca: '원인 분석', capa: '개선 조치', pythonApp: 'Python 앱', skill: '기술' },  
  'fr-FR': { name: 'Français', app: 'ASNS (Système Nerveux Sensoriel AI)', connect: 'Connexion', store: 'Boutique', devices: 'Appareils', dash: 'Tableau', dev: 'Outils', status: 'Statut', cpu: 'CPU', ram: 'RAM', ssd: 'Vie SSD', online: 'En ligne', offline: 'Hors ligne', install: 'Installer', l1: 'Sensoriel', l2: 'Transmission', l3: 'Cognition', sync: 'Sync', nickname: 'Pseudo d\'abord', apply: 'Appliquer', diagnosis: 'Rapport AI', rca: 'RCA', capa: 'CAPA', pythonApp: 'App Python', skill: 'Compétence' },  
  'de-DE': { name: 'Deutsch', app: 'ASNS (Sensorisches Nervensystem AI)', connect: 'Verbindung', store: 'Laden', devices: 'Geräte', dash: 'Dashboard', dev: 'Tools', status: 'Status', cpu: 'CPU', ram: 'RAM', ssd: 'SSD Leben', online: 'Online', offline: 'Offline', install: 'Installieren', l1: 'Sensorik', l2: 'Übertragung', l3: 'Kognition', sync: 'Sync', nickname: 'Spitzname zuerst', apply: 'Speichern', diagnosis: 'KI-Bericht', rca: 'RCA', capa: 'CAPA', pythonApp: 'Python App', skill: 'Fähigkeit' },  
  'vi-VN': { name: 'Tiếng Việt', app: 'ASNS (Hệ Thần Kinh Cảm Biến AI)', connect: 'Kết nối', store: 'Cửa hàng', devices: 'Thiết bị', dash: 'Bảng điều khiển', dev: 'Công cụ', status: 'Trạng thái', cpu: 'CPU', ram: 'RAM', ssd: 'Tuổi thọ SSD', online: 'Trực tuyến', offline: 'Ngoại tuyến', install: 'Cài đặt', l1: 'Cảm biến', l2: 'Truyền dẫn', l3: 'Nhận thức', sync: 'Đồng bộ', nickname: 'Ưu tiên biệt danh', apply: 'Áp dụng', diagnosis: 'Báo cáo AI', rca: 'RCA', capa: 'CAPA', pythonApp: 'Ứng dụng Python', skill: 'Kỹ năng' },  
  'th-TH': { name: 'ไทย', app: 'ASNS (ระบบประสาทรับความรู้สึก AI)', connect: 'การเชื่อมต่อ', store: 'ร้านค้า', devices: 'อุปกรณ์', dash: 'แผงควบคุม', dev: 'เครื่องมือ', status: 'สถานะ', cpu: 'CPU', ram: 'RAM', ssd: 'อายุ SSD', online: 'ออนไลน์', offline: 'ออฟไลน์', install: 'ติดตั้ง', l1: 'ประสาทสัมผัส', l2: 'การส่งข้อมูล', l3: 'ความรู้ความเข้าใจ', sync: 'ซิงค์', nickname: 'ชื่อเล่นก่อน', apply: 'ใช้', diagnosis: 'รายงาน AI', rca: 'RCA', capa: 'CAPA', pythonApp: 'แอป Python', skill: 'ทักษะ' },  
  'id-ID': { name: 'Indonesia', app: 'ASNS (Sistem Saraf Sensorik AI)', connect: 'Koneksi', store: 'Toko', devices: 'Perangkat', dash: 'Dasbor', dev: 'Alat', status: 'Status', cpu: 'CPU', ram: 'RAM', ssd: 'Umur SSD', online: 'Online', offline: 'Offline', install: 'Pasang', l1: 'Sensorik', l2: 'Transmisi', l3: 'Kognitif', sync: 'Sinkron', nickname: 'Alias Prioritas', apply: 'Terapkan', diagnosis: 'Laporan AI', rca: 'RCA', capa: 'CAPA', pythonApp: 'Aplikasi Python', skill: 'Keterampilan' }  
};  

const hostI18n: Record<string, Record<string, string>> = {
  'zh-TW': {
    endpoint: 'EDC URL',
    username: '帳戶名',
    password: '密碼',
    openApp: '打開應用',
    hostedApp: '宿主應用',
    storeIntro: '在 ASNS 宿主中安裝與打開業務應用，先完成宿主與應用的串聯。',
    embeddedHint: '目前先以宿主內嵌方式串聯，方便確認應用商店、已安裝應用與業務頁面的整體關係。',
    openInNewWindow: '新視窗打開',
    apiConnection: 'API 連線',
    apiConnectionDesc: '由 ASNS 宿主層負責與 EDC 後台建立系統級連線，應用層只消費已連進來的資料來源。',
    connectSource: '連線來源',
    connectSourceDesc: '輸入 EDC 位址、帳戶與密碼，建立宿主層連線。',
    testConnection: '測試連線',
    syncChannels: '同步通道',
    lastSync: '最近同步',
    connectedMachine: '已連接節點',
    mappingWorkbench: '通道工作台',
    mappingWorkbenchDesc: '宿主層先把硬體通道讀進來並整理成採集清單，後續應用再從這份清單裡做自己的配置。',
    hardwareCollectionWorkbench: '硬體通道採集',
    sourceCatalog: '來源通道目錄',
    sourceCatalogDesc: '直接從硬體讀取原始通道，支援逐條加入或整組加入，方便先建立可用資料清單。',
    addedChannels: '已添加通道清單',
    addedChannelsDesc: '這裡先收集宿主層要保留的硬體通道；應用商店內的各個應用之後再從這份清單挑選自己要用的欄位。',
    searchPlaceholder: '搜尋設備、區域、通道名稱或 suid/cuid',
    channelAddHint: '左側每條通道都可以直接加入，設備組也支援整組加入。',
    saveDraft: '保存草稿',
    required: '必填',
    mapped: '已映射',
    unmapped: '未映射',
    sourceDevice: '來源設備',
    sourceChannel: '來源通道',
    noResult: '沒有符合搜尋條件的通道',
    assignNow: '選中查看',
    addCurrent: '添加此通道',
    addGroup: '整組添加',
    added: '已添加',
    alreadyAdded: '已在清單',
    removeCurrent: '移除這條',
    removeGroup: '移除整組',
    sourceDetailLabel: '通道詳情',
    selectedChannel: '當前選中通道',
    selectedChannelDesc: '查看通道明細、最近值，以及它是否已經加入宿主層採集清單。',
    collectionStatus: '加入狀態',
    alreadyInCollection: '這條通道已經在宿主層採集清單裡。',
    notInCollectionYet: '這條通道還沒有加入宿主層採集清單。',
    sourceReadonly: '只讀目錄',
    sourceRealtime: '宿主直連',
    enabledChannels: '使能通道',
    connectionReady: 'EDC 連線就緒',
    waitingValidation: '等待驗證',
    testSuccess: '連線測試成功，已取得設備清單摘要。',
    testFailed: '連線測試失敗',
    syncSuccess: '通道清單同步完成，已更新宿主目錄。',
    syncFailed: '同步失敗',
    selectedEmpty: '請先從左側選擇一條通道',
    hostConnectNote: '宿主層只負責後台連線、同步與標準化，後續各業務應用共享同一份連線能力。',
    hostCollectionNote: '這一頁先做宿主層硬體通道收集，不直接處理各個應用的欄位映射。',
    collectionExplain: '先把硬體通道加入宿主清單，之後各應用再從這份清單裡綁自己的欄位。',
    noAddedChannels: '目前還沒有加入任何硬體通道。',
    channelCountLabel: 'channels',
    draftSaved: '草稿已保存，時間：',
    settingsAppliedMessage: '設定已保存，時間：',
    settingsSyncFailed: '設定同步失敗，請稍後重試。',
    draftRestored: '已恢復上次保存的草稿，時間：',
    draftRestoreFailed: '上次保存的草稿無法恢復，請重新保存。',
    sourceSwitchTitle: '換源確認',
    sourceSwitchHeading: '切換新的 EDC 資料來源',
    sourceSwitchPromptPrefix: '繼續執行「',
    sourceSwitchPromptSuffix: '」前，系統將先清除目前來源相關配置。',
    sourceSwitchTargetLabel: '目標來源',
    sourceSwitchResetSummary: '這會清掉目前來源下的宿主已添加通道、同步目錄快取、活動基線、基線通道綁定與宿主連線摘要。',
    sourceSwitchResetList: '清除後需要重新測試連線、重新同步通道，並由業務應用重新完成欄位綁定。',
    cancelSourceSwitch: '取消',
    confirmSourceSwitch: '確認切換',
    sourceSwitchCancelled: '已取消換源，本次操作未執行。',
  },
  'zh-CN': {
    endpoint: 'EDC URL',
    username: '账户名',
    password: '密码',
    openApp: '打开应用',
    hostedApp: '宿主应用',
    storeIntro: '在 ASNS 宿主中安装与打开业务应用，先完成宿主与应用的串联。',
    embeddedHint: '目前先以宿主内嵌方式串联，方便确认应用商店、已安装应用与业务页面的整体关系。',
    openInNewWindow: '新窗口打开',
    apiConnection: 'API 连接',
    apiConnectionDesc: '由 ASNS 宿主层负责与 EDC 后台建立系统级连接，应用层只消费已连进来的数据来源。',
    connectSource: '连接来源',
    connectSourceDesc: '输入 EDC 地址、账户与密码，建立宿主层连接。',
    testConnection: '测试连接',
    syncChannels: '同步通道',
    lastSync: '最近同步',
    connectedMachine: '已连接节点',
    mappingWorkbench: '通道工作台',
    mappingWorkbenchDesc: '宿主层先把硬件通道读进来并整理成采集清单，后续应用再从这份清单里做自己的配置。',
    hardwareCollectionWorkbench: '硬件通道采集',
    sourceCatalog: '来源通道目录',
    sourceCatalogDesc: '直接从硬件读取原始通道，支持逐条加入或整组加入，方便先建立可用数据清单。',
    addedChannels: '已添加通道清单',
    addedChannelsDesc: '这里先收集宿主层要保留的硬件通道；应用商店内的各个应用之后再从这份清单挑选自己要用的字段。',
    searchPlaceholder: '搜索设备、区域、通道名称或 suid/cuid',
    channelAddHint: '左侧每条通道都可以直接加入，设备组也支持整组加入。',
    saveDraft: '保存草稿',
    required: '必填',
    mapped: '已映射',
    unmapped: '未映射',
    sourceDevice: '来源设备',
    sourceChannel: '来源通道',
    noResult: '没有符合搜索条件的通道',
    assignNow: '选中查看',
    addCurrent: '添加此通道',
    addGroup: '整组添加',
    added: '已添加',
    alreadyAdded: '已在清单',
    removeCurrent: '移除这条',
    removeGroup: '移除整组',
    sourceDetailLabel: '通道详情',
    selectedChannel: '当前选中通道',
    selectedChannelDesc: '查看通道明细、最近值，以及它是否已经加入宿主层采集清单。',
    collectionStatus: '加入状态',
    alreadyInCollection: '这条通道已经在宿主层采集清单里。',
    notInCollectionYet: '这条通道还没有加入宿主层采集清单。',
    sourceReadonly: '只读目录',
    sourceRealtime: '宿主直连',
    enabledChannels: '使能通道',
    connectionReady: 'EDC 连接就绪',
    waitingValidation: '等待验证',
    testSuccess: '连接测试成功，已取得设备清单摘要。',
    testFailed: '连接测试失败',
    syncSuccess: '通道清单同步完成，已更新宿主目录。',
    syncFailed: '同步失败',
    selectedEmpty: '请先从左侧选择一条通道',
    hostConnectNote: '宿主层只负责后台连接、同步与标准化，后续各业务应用共享同一份连接能力。',
    hostCollectionNote: '这一页先做宿主层硬件通道收集，不直接处理各个应用的字段映射。',
    collectionExplain: '先把硬件通道加入宿主清单，之后各应用再从这份清单里绑自己的字段。',
    noAddedChannels: '目前还没有加入任何硬件通道。',
    channelCountLabel: 'channels',
    draftSaved: '草稿已保存，时间：',
    settingsAppliedMessage: '设置已保存，时间：',
    settingsSyncFailed: '设置同步失败，请稍后重试。',
    draftRestored: '已恢复上次保存的草稿，时间：',
    draftRestoreFailed: '上次保存的草稿无法恢复，请重新保存。',
    sourceSwitchTitle: '换源确认',
    sourceSwitchHeading: '切换新的 EDC 数据源',
    sourceSwitchPromptPrefix: '继续执行“',
    sourceSwitchPromptSuffix: '”前，系统将先清除当前源相关配置。',
    sourceSwitchTargetLabel: '目标来源',
    sourceSwitchResetSummary: '这会清掉当前源下的宿主已添加通道、同步目录缓存、活动基线、基线通道绑定与宿主连接摘要。',
    sourceSwitchResetList: '清除后需要重新测试连接、重新同步通道，并由业务应用重新完成字段绑定。',
    cancelSourceSwitch: '取消',
    confirmSourceSwitch: '确认切换',
    sourceSwitchCancelled: '已取消换源，本次操作未执行。',
  },
  'en-US': {
    endpoint: 'EDC URL',
    username: 'Username',
    password: 'Password',
    openApp: 'Open App',
    hostedApp: 'Hosted App',
    storeIntro: 'Install and open business apps inside ASNS first, then iterate on the embedded experience.',
    embeddedHint: 'The host currently embeds the business app so we can validate store, installed-app entry, and page flow together.',
    openInNewWindow: 'Open in New Window',
    apiConnection: 'API Connection',
    apiConnectionDesc: 'ASNS owns the system-level connection to EDC. The app only consumes the connected data sources.',
    connectSource: 'Connection Source',
    connectSourceDesc: 'Enter EDC URL, username, and password to establish the host-level connection.',
    testConnection: 'Test Connection',
    syncChannels: 'Sync Channels',
    lastSync: 'Last Sync',
    connectedMachine: 'Connected Node',
    mappingWorkbench: 'Channel Workbench',
    mappingWorkbenchDesc: 'The host first reads hardware channels into a shared collection. Each installed app will later map its own fields from that collection.',
    hardwareCollectionWorkbench: 'Hardware Channel Intake',
    sourceCatalog: 'Source Catalog',
    sourceCatalogDesc: 'Read raw hardware channels directly and support adding one-by-one or by device group.',
    addedChannels: 'Added Channel Collection',
    addedChannelsDesc: 'The host keeps a reusable hardware channel collection here. Installed apps will later pick their own fields from it.',
    searchPlaceholder: 'Search by device, area, channel name, or suid/cuid',
    channelAddHint: 'Each row can be added directly, and each device group also supports bulk add.',
    saveDraft: 'Save Draft',
    required: 'Required',
    mapped: 'Mapped',
    unmapped: 'Unmapped',
    sourceDevice: 'Device',
    sourceChannel: 'Channel',
    noResult: 'No channels match the current search',
    assignNow: 'Inspect',
    addCurrent: 'Add Channel',
    addGroup: 'Add Group',
    added: 'Added',
    alreadyAdded: 'Already Added',
    removeCurrent: 'Remove',
    removeGroup: 'Remove Group',
    sourceDetailLabel: 'Channel Details',
    selectedChannel: 'Selected Channel',
    selectedChannelDesc: 'Review channel details, the latest sample, and whether this channel is already in the host collection.',
    collectionStatus: 'Collection Status',
    alreadyInCollection: 'This channel is already included in the host-level collection.',
    notInCollectionYet: 'This channel has not been added to the host-level collection yet.',
    sourceReadonly: 'Readonly Catalog',
    sourceRealtime: 'Live via Host',
    enabledChannels: 'Enabled Channels',
    connectionReady: 'EDC Link Ready',
    waitingValidation: 'Waiting for Validation',
    testSuccess: 'Connection test succeeded and returned a device summary.',
    testFailed: 'Connection test failed',
    syncSuccess: 'Channel sync completed and refreshed the host catalog.',
    syncFailed: 'Channel sync failed',
    selectedEmpty: 'Choose one channel from the left first',
    hostConnectNote: 'The host owns connectivity, synchronization, and standardization so every installed app can reuse one shared connection.',
    hostCollectionNote: 'This page only collects reusable hardware channels at the host layer. App field mapping will happen later inside each installed app.',
    collectionExplain: 'First add hardware channels into the host collection. Each app will later map its own business fields from this shared list.',
    noAddedChannels: 'No hardware channels have been added yet.',
    channelCountLabel: 'channels',
    draftSaved: 'Draft saved at',
    settingsAppliedMessage: 'Settings saved at',
    settingsSyncFailed: 'Settings sync failed. Please try again later.',
    draftRestored: 'Restored the previous draft from',
    draftRestoreFailed: 'The previous draft could not be restored. Please save again.',
    sourceSwitchTitle: 'Source Switch',
    sourceSwitchHeading: 'Switch to a new EDC source',
    sourceSwitchPromptPrefix: 'Before continuing with "',
    sourceSwitchPromptSuffix: '", the system will clear the current source-bound configuration.',
    sourceSwitchTargetLabel: 'Target Source',
    sourceSwitchResetSummary: 'This clears the host channel collection, synced catalog cache, active baseline, baseline channel bindings, and host connectivity summary for the current source.',
    sourceSwitchResetList: 'After the reset, test the connection again, resync channels, and remap business fields in the installed apps.',
    cancelSourceSwitch: 'Cancel',
    confirmSourceSwitch: 'Confirm Switch',
    sourceSwitchCancelled: 'Source switch cancelled. No changes were applied.',
  },
};

const entryI18n: Record<string, Record<string, string>> = {
  'zh-TW': {
    appStudio: '應用工作室',
    aiCreator: 'AI Creator',
    hostedApp: '宿主應用',
    openApp: '打開應用',
    storeIntro: '在 ASNS 宿主中安裝與打開業務應用，先完成宿主與應用的串聯。',
    embeddedHint: '目前先以宿主內嵌方式串聯，方便確認應用商店、已安裝應用與業務頁面的整體關係。',
    openInNewWindow: '新視窗打開',
    edcElectricityDesc: '中頻爐熔煉偏差監控與基線分析應用，將作為 ASNS 應用商店中的已安裝業務應用提供。',
    powerMatrixDesc: 'Python 清洗應用：負責將 RocksDB 原始電力流轉化為特徵 JSON。',
    openclawExpertDesc: 'L3 診斷技能：馬達壽命預測、機電故障 RCA 分析。',
    studioIntro: '輸入應用名稱，AI 將自動為您生成專屬圖示與智慧配圖。',
    studioAppName: '應用名稱',
    studioAppNamePlaceholder: '例如：智慧能源監控...',
    studioDescription: '功能描述',
    studioDescriptionPlaceholder: '描述應用的主要功能，AI 將以此構思視覺...',
    studioGeneratingConcept: 'AI 正在構思應用視覺與功能...',
    studioGeneratingIcon: '正在生成智慧圖示...',
    studioGeneratingFeature: '正在生成智慧配圖...',
    studioGenerateDone: '生成完成！',
    studioGenerateFailed: '生成失敗，請檢查網路或 API 設定。',
    studioGenerateAction: '開始 AI 自動生成',
    studioGeneratingAction: 'AI 正在創作中...',
    studioPreview: '生成預覽',
    iconPreview: '圖示預覽',
    featurePreview: '配圖預覽',
  },
  'zh-CN': {
    appStudio: '应用工作室',
    aiCreator: 'AI Creator',
    hostedApp: '宿主应用',
    openApp: '打开应用',
    storeIntro: '在 ASNS 宿主中安装与打开业务应用，先完成宿主与应用的串联。',
    embeddedHint: '目前先以宿主内嵌方式串联，方便确认应用商店、已安装应用与业务页面的整体关系。',
    openInNewWindow: '新窗口打开',
    edcElectricityDesc: '中频炉熔炼偏差监控与基线分析应用，将作为 ASNS 应用商店中的已安装业务应用提供。',
    powerMatrixDesc: 'Python 清洗应用：负责将 RocksDB 原始电力流转化为特征 JSON。',
    openclawExpertDesc: 'L3 诊断技能：电机寿命预测、机电故障 RCA 分析。',
    studioIntro: '输入应用名称，AI 将自动为你生成专属图标与智慧配图。',
    studioAppName: '应用名称',
    studioAppNamePlaceholder: '例如：智慧能源监控...',
    studioDescription: '功能描述',
    studioDescriptionPlaceholder: '描述应用的主要功能，AI 将据此构思视觉...',
    studioGeneratingConcept: 'AI 正在构思应用视觉与功能...',
    studioGeneratingIcon: '正在生成智慧图标...',
    studioGeneratingFeature: '正在生成智慧配图...',
    studioGenerateDone: '生成完成！',
    studioGenerateFailed: '生成失败，请检查网络或 API 设置。',
    studioGenerateAction: '开始 AI 自动生成',
    studioGeneratingAction: 'AI 正在创作中...',
    studioPreview: '生成预览',
    iconPreview: '图标预览',
    featurePreview: '配图预览',
  },
  'en-US': {
    appStudio: 'App Studio',
    aiCreator: 'AI Creator',
    hostedApp: 'Hosted App',
    openApp: 'Open App',
    storeIntro: 'Install and open business apps inside ASNS first, then complete the host-to-app integration flow.',
    embeddedHint: 'The host currently embeds the business app so the store, installed entry, and business page flow can be validated together.',
    openInNewWindow: 'Open in New Window',
    edcElectricityDesc: 'Mid-frequency furnace deviation monitoring and baseline analysis, delivered as an installed business app inside the ASNS store.',
    powerMatrixDesc: 'Python cleaning app that converts raw RocksDB power streams into feature JSON payloads.',
    openclawExpertDesc: 'L3 diagnostic skill for motor lifetime prediction and electromechanical RCA analysis.',
    studioIntro: 'Enter an app name and AI will generate a dedicated icon and feature artwork for it.',
    studioAppName: 'App Name',
    studioAppNamePlaceholder: 'Example: Smart Energy Monitor...',
    studioDescription: 'Description',
    studioDescriptionPlaceholder: 'Describe the main capabilities so AI can shape the visual direction...',
    studioGeneratingConcept: 'AI is drafting the app concept and visuals...',
    studioGeneratingIcon: 'Generating the icon...',
    studioGeneratingFeature: 'Generating the feature artwork...',
    studioGenerateDone: 'Generation complete.',
    studioGenerateFailed: 'Generation failed. Check network or API settings.',
    studioGenerateAction: 'Start AI Generation',
    studioGeneratingAction: 'AI Generating...',
    studioPreview: 'AI Preview',
    iconPreview: 'Icon Preview',
    featurePreview: 'Feature Preview',
  },
  'ja-JP': {
    appStudio: 'アプリスタジオ',
    aiCreator: 'AI Creator',
    hostedApp: 'ホストアプリ',
    openApp: 'アプリを開く',
    storeIntro: 'まず ASNS ホスト内で業務アプリを導入して開き、ホストとアプリの連携を確認します。',
    embeddedHint: '現在はホスト埋め込みで接続し、ストア、導入済みアプリ入口、業務画面の流れをまとめて確認します。',
    openInNewWindow: '新しいウィンドウで開く',
    edcElectricityDesc: '中周波炉の偏差監視と基準線分析を行う業務アプリで、ASNS ストアの導入済みアプリとして提供されます。',
    powerMatrixDesc: 'RocksDB の生電力データを特徴量 JSON に変換する Python クレンジングアプリです。',
    openclawExpertDesc: 'モーター寿命予測と電機故障 RCA を行う L3 診断スキルです。',
    studioIntro: 'アプリ名を入力すると、AI が専用アイコンとキービジュアルを自動生成します。',
    studioAppName: 'アプリ名',
    studioAppNamePlaceholder: '例：スマートエネルギー監視...',
    studioDescription: '機能説明',
    studioDescriptionPlaceholder: '主要機能を入力すると、AI がビジュアル方向を考案します...',
    studioGeneratingConcept: 'AI がアプリの構想とビジュアルを作成中です...',
    studioGeneratingIcon: 'アイコンを生成中...',
    studioGeneratingFeature: 'キービジュアルを生成中...',
    studioGenerateDone: '生成が完了しました。',
    studioGenerateFailed: '生成に失敗しました。ネットワークまたは API 設定を確認してください。',
    studioGenerateAction: 'AI で自動生成',
    studioGeneratingAction: 'AI が生成中...',
    studioPreview: '生成プレビュー',
    iconPreview: 'アイコンプレビュー',
    featurePreview: 'ビジュアルプレビュー',
  },
  'ko-KR': {
    appStudio: '앱 스튜디오',
    aiCreator: 'AI Creator',
    hostedApp: '호스트 앱',
    openApp: '앱 열기',
    storeIntro: '먼저 ASNS 호스트 안에서 업무 앱을 설치하고 열어 호스트와 앱의 연동을 확인합니다.',
    embeddedHint: '현재는 호스트 내장 방식으로 연결하여 스토어, 설치된 앱 진입점, 업무 페이지 흐름을 함께 검증합니다.',
    openInNewWindow: '새 창에서 열기',
    edcElectricityDesc: '중주파 용해 편차 모니터링과 기준선 분석을 제공하는 업무 앱으로 ASNS 스토어의 설치형 앱으로 제공됩니다.',
    powerMatrixDesc: 'RocksDB 원시 전력 스트림을 특징 JSON 으로 변환하는 Python 정제 앱입니다.',
    openclawExpertDesc: '모터 수명 예측과 전기기계 고장 RCA 분석을 위한 L3 진단 스킬입니다.',
    studioIntro: '앱 이름을 입력하면 AI 가 전용 아이콘과 피처 이미지를 자동 생성합니다.',
    studioAppName: '앱 이름',
    studioAppNamePlaceholder: '예: 스마트 에너지 모니터...',
    studioDescription: '기능 설명',
    studioDescriptionPlaceholder: '주요 기능을 설명하면 AI 가 시각 방향을 구성합니다...',
    studioGeneratingConcept: 'AI 가 앱 컨셉과 비주얼을 구상 중입니다...',
    studioGeneratingIcon: '아이콘 생성 중...',
    studioGeneratingFeature: '피처 이미지 생성 중...',
    studioGenerateDone: '생성이 완료되었습니다.',
    studioGenerateFailed: '생성에 실패했습니다. 네트워크 또는 API 설정을 확인하세요.',
    studioGenerateAction: 'AI 자동 생성 시작',
    studioGeneratingAction: 'AI 생성 중...',
    studioPreview: '생성 미리보기',
    iconPreview: '아이콘 미리보기',
    featurePreview: '피처 이미지 미리보기',
  },
  'fr-FR': {
    appStudio: 'Studio d\'applications',
    aiCreator: 'AI Creator',
    hostedApp: 'Application hote',
    openApp: 'Ouvrir l\'application',
    storeIntro: 'Installez puis ouvrez les applications metier dans l\'hote ASNS afin de valider d\'abord l\'integration hote-application.',
    embeddedHint: 'L\'hote integre pour l\'instant l\'application metier afin de verifier ensemble le store, l\'entree des applications installees et le flux des pages.',
    openInNewWindow: 'Ouvrir dans une nouvelle fenetre',
    edcElectricityDesc: 'Application metier de surveillance des ecarts de fusion et d\'analyse de ligne de base pour four MF, fournie comme application installee dans le store ASNS.',
    powerMatrixDesc: 'Application Python de nettoyage qui convertit les flux electriques bruts de RocksDB en JSON de caracteristiques.',
    openclawExpertDesc: 'Competence de diagnostic L3 pour la prediction de duree de vie moteur et l\'analyse RCA electromechanique.',
    studioIntro: 'Saisissez un nom d\'application et l\'IA generera automatiquement une icone et un visuel dedies.',
    studioAppName: 'Nom de l\'application',
    studioAppNamePlaceholder: 'Exemple : Supervision energie intelligente...',
    studioDescription: 'Description',
    studioDescriptionPlaceholder: 'Decrivez les fonctions principales pour guider le style visuel...',
    studioGeneratingConcept: 'L\'IA prepare le concept et les visuels de l\'application...',
    studioGeneratingIcon: 'Generation de l\'icone...',
    studioGeneratingFeature: 'Generation du visuel principal...',
    studioGenerateDone: 'Generation terminee.',
    studioGenerateFailed: 'La generation a echoue. Verifiez le reseau ou la configuration API.',
    studioGenerateAction: 'Lancer la generation IA',
    studioGeneratingAction: 'Generation IA en cours...',
    studioPreview: 'Apercu IA',
    iconPreview: 'Apercu de l\'icone',
    featurePreview: 'Apercu du visuel',
  },
  'de-DE': {
    appStudio: 'App Studio',
    aiCreator: 'AI Creator',
    hostedApp: 'Host-App',
    openApp: 'App offnen',
    storeIntro: 'Installieren und offnen Sie Geschaftsanwendungen zuerst im ASNS-Host, um die Host-App-Integration zu validieren.',
    embeddedHint: 'Die Fachanwendung wird derzeit im Host eingebettet, damit Store, installierter Einstieg und Seitenfluss gemeinsam gepruft werden konnen.',
    openInNewWindow: 'In neuem Fenster offnen',
    edcElectricityDesc: 'Fachanwendung fur Abweichungsuberwachung und Baseline-Analyse im Mittelfrequenz-Schmelzprozess, bereitgestellt als installierte App im ASNS-Store.',
    powerMatrixDesc: 'Python-Bereinigungsanwendung, die rohe RocksDB-Leistungsdaten in Feature-JSON umwandelt.',
    openclawExpertDesc: 'L3-Diagnose-Skill fur Motorlebensdauer-Prognosen und elektromechanische RCA-Analysen.',
    studioIntro: 'Geben Sie einen App-Namen ein und die KI erstellt automatisch ein Icon und ein Titelbild.',
    studioAppName: 'App-Name',
    studioAppNamePlaceholder: 'Beispiel: Intelligente Energieuberwachung...',
    studioDescription: 'Beschreibung',
    studioDescriptionPlaceholder: 'Beschreiben Sie die Hauptfunktionen, damit die KI die visuelle Richtung ableiten kann...',
    studioGeneratingConcept: 'Die KI entwirft gerade Konzept und Visuals...',
    studioGeneratingIcon: 'Icon wird erzeugt...',
    studioGeneratingFeature: 'Titelbild wird erzeugt...',
    studioGenerateDone: 'Erzeugung abgeschlossen.',
    studioGenerateFailed: 'Erzeugung fehlgeschlagen. Bitte Netzwerk oder API-Einstellungen prufen.',
    studioGenerateAction: 'KI-Generierung starten',
    studioGeneratingAction: 'KI generiert...',
    studioPreview: 'Vorschau',
    iconPreview: 'Icon-Vorschau',
    featurePreview: 'Bild-Vorschau',
  },
  'vi-VN': {
    appStudio: 'Xuong ung dung',
    aiCreator: 'AI Creator',
    hostedApp: 'Ung dung chu',
    openApp: 'Mo ung dung',
    storeIntro: 'Hay cai dat va mo ung dung nghiep vu trong ASNS truoc de xac nhan luong tich hop giua host va app.',
    embeddedHint: 'Hien tai host nhung truc tiep ung dung nghiep vu de kiem tra dong thoi cua hang, diem vao da cai dat va luong trang.',
    openInNewWindow: 'Mo trong cua so moi',
    edcElectricityDesc: 'Ung dung giam sat do lech nau luyen va phan tich duong co so cho lo trung tan, duoc cung cap nhu mot ung dung da cai trong ASNS Store.',
    powerMatrixDesc: 'Ung dung Python lam sach du lieu, chuyen luong dien tho RocksDB thanh JSON dac trung.',
    openclawExpertDesc: 'Ky nang chan doan L3 cho du bao tuoi tho dong co va phan tich RCA co dien.',
    studioIntro: 'Nhap ten ung dung va AI se tu dong tao bieu tuong cung anh gioi thieu rieng.',
    studioAppName: 'Ten ung dung',
    studioAppNamePlaceholder: 'Vi du: Giam sat nang luong thong minh...',
    studioDescription: 'Mo ta chuc nang',
    studioDescriptionPlaceholder: 'Mo ta cac kha nang chinh de AI dinh huong giao dien...',
    studioGeneratingConcept: 'AI dang phac thao y tuong va hinh anh ung dung...',
    studioGeneratingIcon: 'Dang tao bieu tuong...',
    studioGeneratingFeature: 'Dang tao anh gioi thieu...',
    studioGenerateDone: 'Da tao xong.',
    studioGenerateFailed: 'Tao that bai. Vui long kiem tra mang hoac cau hinh API.',
    studioGenerateAction: 'Bat dau tao bang AI',
    studioGeneratingAction: 'AI dang tao...',
    studioPreview: 'Xem truoc',
    iconPreview: 'Xem truoc bieu tuong',
    featurePreview: 'Xem truoc anh',
  },
  'th-TH': {
    appStudio: 'สตูดิโอแอป',
    aiCreator: 'AI Creator',
    hostedApp: 'แอปโฮสต์',
    openApp: 'เปิดแอป',
    storeIntro: 'ติดตั้งและเปิดแอปธุรกิจใน ASNS โฮสต์ก่อน เพื่อยืนยันลำดับการเชื่อมต่อระหว่างโฮสต์กับแอป',
    embeddedHint: 'ขณะนี้โฮสต์ฝังแอปธุรกิจไว้ภายใน เพื่อให้ตรวจสอบสโตร์ จุดเข้าแอปที่ติดตั้ง และโฟลว์หน้าจอร่วมกันได้',
    openInNewWindow: 'เปิดในหน้าต่างใหม่',
    edcElectricityDesc: 'แอปสำหรับติดตามความเบี่ยงเบนการหลอมและวิเคราะห์เส้นฐานของเตาความถี่ปานกลาง ให้ใช้งานเป็นแอปที่ติดตั้งใน ASNS Store',
    powerMatrixDesc: 'แอป Python สำหรับทำความสะอาดข้อมูล เปลี่ยนสตรีมพลังงานดิบจาก RocksDB ให้เป็น JSON คุณลักษณะ',
    openclawExpertDesc: 'ทักษะวินิจฉัย L3 สำหรับพยากรณ์อายุมอเตอร์และวิเคราะห์ RCA ทางไฟฟ้ากล',
    studioIntro: 'ใส่ชื่อแอป แล้ว AI จะสร้างไอคอนและภาพประกอบหลักให้โดยอัตโนมัติ',
    studioAppName: 'ชื่อแอป',
    studioAppNamePlaceholder: 'เช่น Smart Energy Monitor...',
    studioDescription: 'คำอธิบาย',
    studioDescriptionPlaceholder: 'อธิบายความสามารถหลักเพื่อให้ AI ออกแบบทิศทางภาพ...',
    studioGeneratingConcept: 'AI กำลังร่างแนวคิดและภาพของแอป...',
    studioGeneratingIcon: 'กำลังสร้างไอคอน...',
    studioGeneratingFeature: 'กำลังสร้างภาพประกอบหลัก...',
    studioGenerateDone: 'สร้างเสร็จแล้ว',
    studioGenerateFailed: 'สร้างไม่สำเร็จ โปรดตรวจสอบเครือข่ายหรือการตั้งค่า API',
    studioGenerateAction: 'เริ่มสร้างด้วย AI',
    studioGeneratingAction: 'AI กำลังสร้าง...',
    studioPreview: 'ตัวอย่าง',
    iconPreview: 'ตัวอย่างไอคอน',
    featurePreview: 'ตัวอย่างภาพ',
  },
  'id-ID': {
    appStudio: 'Studio Aplikasi',
    aiCreator: 'AI Creator',
    hostedApp: 'Aplikasi Host',
    openApp: 'Buka Aplikasi',
    storeIntro: 'Pasang dan buka aplikasi bisnis di dalam host ASNS lebih dulu untuk memvalidasi alur integrasi host-ke-aplikasi.',
    embeddedHint: 'Saat ini host menyematkan aplikasi bisnis agar alur store, entri aplikasi terpasang, dan halaman bisnis dapat divalidasi bersama.',
    openInNewWindow: 'Buka di Jendela Baru',
    edcElectricityDesc: 'Aplikasi bisnis untuk memantau deviasi peleburan dan analisis baseline tungku frekuensi menengah, disajikan sebagai aplikasi terpasang di ASNS Store.',
    powerMatrixDesc: 'Aplikasi pembersihan Python yang mengubah aliran daya mentah RocksDB menjadi payload JSON fitur.',
    openclawExpertDesc: 'Keahlian diagnostik L3 untuk prediksi umur motor dan analisis RCA elektromekanis.',
    studioIntro: 'Masukkan nama aplikasi dan AI akan membuat ikon serta artwork fitur secara otomatis.',
    studioAppName: 'Nama Aplikasi',
    studioAppNamePlaceholder: 'Contoh: Monitor Energi Cerdas...',
    studioDescription: 'Deskripsi',
    studioDescriptionPlaceholder: 'Jelaskan kemampuan utama agar AI dapat menentukan arah visual...',
    studioGeneratingConcept: 'AI sedang menyusun konsep dan visual aplikasi...',
    studioGeneratingIcon: 'Sedang membuat ikon...',
    studioGeneratingFeature: 'Sedang membuat artwork fitur...',
    studioGenerateDone: 'Pembuatan selesai.',
    studioGenerateFailed: 'Pembuatan gagal. Periksa jaringan atau pengaturan API.',
    studioGenerateAction: 'Mulai Generasi AI',
    studioGeneratingAction: 'AI Sedang Membuat...',
    studioPreview: 'Pratinjau',
    iconPreview: 'Pratinjau Ikon',
    featurePreview: 'Pratinjau Gambar',
  },
};

interface AppWindow {
  id: string;
  name: string;
  icon?: React.ReactNode;
  iconUrl?: string;
  color: string;
  description?: string;
  kind?: 'system' | 'embedded';
  launchUrl?: string;
}

interface WindowProps {
  win: AppWindow;
  active: boolean;
  onFocus: () => void;
  onClose: () => void;
  theme: string;
  children: React.ReactNode;
}

interface Sensor {
  suid: string;
  name: string;
  nickname: string;
  value: number;
  unit: string;
}

interface SensorGroup {
  cuid: string;
  nickname: string;
  status: string;
  sensors: Sensor[];
}

interface Config {
  endpoint: string;
  username: string;
  password: string;
}

interface DeviceViewProps {
  sensors: SensorGroup[];
  getLabel: (item: any) => string;
  t: (key: string) => string;
}

interface StoreViewProps {
  t: (key: string) => string;
  items: StoreItem[];
  installedAppIds: string[];
  onInstall: (appId: string) => void;
  onOpen: (appId: string) => void;
}

interface StoreItem extends AppWindow {
  type: 'py' | 'md' | 'app';
  status: 'deployable' | 'ready' | 'installed';
}

interface AppStudioViewProps {
  t: (key: string) => string;
  onAddApp: (app: AppWindow) => void;
}

type AppRuntimeGlobals = typeof globalThis & {
  __ASNS_EDC_APP_URL__?: string;
};

function resolveEmbeddedEdcUrl(): string {
  const runtimeGlobals = globalThis as AppRuntimeGlobals;
  return (
    runtimeGlobals.__ASNS_EDC_APP_URL__ ||
    import.meta.env.VITE_ASNS_EDC_APP_URL ||
    (typeof window !== 'undefined' ? new URL('/edc/', window.location.origin).toString() : '/edc/')
  );
}

export default function App() {  
  // 核心狀態  
  const [lang, setLang] = useState('zh-CN');  
  const [theme, setTheme] = useState('light');  
  const [openWindowIds, setOpenWindowIds] = useState<string[]>([]);  
  const [activeWin, setActiveWin] = useState<string | null>(null);  
  const [customApps, setCustomApps] = useState<AppWindow[]>([]);
  const [installedAppIds, setInstalledAppIds] = useState<string[]>(['edc-electricity']);
  const [isConnected, setIsConnected] = useState(false);  
  const [showLangMenu, setShowLangMenu] = useState(false);  
  const embeddedEdcUrl = resolveEmbeddedEdcUrl();
    
  // EDC API 配置狀態  
  const [config, setConfig] = useState<Config>({  
    endpoint: '',
    username: '',
    password: '',
  });  
  
  // 感測器清單 (落實 Nickname 優先邏輯)  
  const [sensors, setSensors] = useState<SensorGroup[]>([  
    { cuid: 'C001', nickname: '一號空壓機房', status: 'active', sensors: [  
      { suid: 'S01', name: 'Main_Power', nickname: '總供電負載', value: 45.8, unit: 'kW' },  
      { suid: 'S02', name: 'Pressure_Tank', nickname: '', value: 7.2, unit: 'bar' }  
    ]},  
    { cuid: 'C002', nickname: '', status: 'active', sensors: [  
      { suid: 'S01', name: 'Motor_Temp', nickname: '馬達溫度', value: 42.5, unit: '°C' },  
      { suid: 'S02', name: 'Vibration_X', nickname: '', value: 0.08, unit: 'g' }  
    ]}  
  ]);  
  
  const t = useCallback(
    (key: string) =>
      hostI18n[lang]?.[key] ||
      entryI18n[lang]?.[key] ||
      translations[lang]?.[key] ||
      hostI18n['zh-CN']?.[key] ||
      entryI18n['en-US']?.[key] ||
      translations['zh-CN']?.[key] ||
      key,
    [lang],
  );  
  
  // 輔助邏輯：Nickname > Name > ID  
  const getLabel = (item: any) => item.nickname || item.name || item.cuid || item.suid;  

  const storeItems: StoreItem[] = [
    {
      id: 'edc-electricity',
      name: 'EDC electricity',
      icon: <Zap className="w-full h-full" />,
      color: 'bg-gradient-to-br from-blue-600 to-cyan-500',
      description: t('edcElectricityDesc'),
      type: 'app',
      status: installedAppIds.includes('edc-electricity') ? 'installed' : 'deployable',
      kind: 'embedded',
      launchUrl: embeddedEdcUrl,
    },
    {
      id: 'l2_cleaner',
      name: 'Power Matrix L2',
      description: t('powerMatrixDesc'),
      type: 'py',
      status: 'deployable',
      color: 'bg-blue-500',
    },
    {
      id: 'l3_expert',
      name: 'OpenClaw Expert',
      description: t('openclawExpertDesc'),
      type: 'md',
      status: 'ready',
      color: 'bg-purple-500',
    },
  ];

  const installedStoreApps = storeItems.filter(item => installedAppIds.includes(item.id));
  
  const appIcons: AppWindow[] = [  
    { id: 'dash', name: t('dash'), icon: <Activity className="w-full h-full" />, color: 'bg-blue-500' },  
    { id: 'store', name: t('store'), icon: <Package className="w-full h-full" />, color: 'bg-orange-500' },  
    { id: 'devices', name: t('devices'), icon: <Database className="w-full h-full" />, color: 'bg-emerald-500' },  
    { id: 'studio', name: t('appStudio'), icon: <Cpu className="w-full h-full" />, color: 'bg-indigo-600' },
    { id: 'connect', name: t('connect'), icon: <Settings className="w-full h-full" />, color: 'bg-slate-600' },  
    ...installedStoreApps,
    ...customApps
  ];  
  
  const openWindows = openWindowIds.map(id => appIcons.find(app => app.id === id)).filter(Boolean) as AppWindow[];

  const toggleWindow = (appId: string) => {
    const nextState = toggleWindowState(openWindowIds, appId);
    setOpenWindowIds(nextState.openWindowIds);
    setActiveWin(nextState.activeWin);
  };

  const installApp = (appId: string) => {
    if (installedAppIds.includes(appId)) {
      return;
    }
    setInstalledAppIds([...installedAppIds, appId]);
  };
  
  return (  
    <div className={`${theme === 'dark' ? 'dark' : ''} h-screen w-full transition-all duration-700 select-none overflow-hidden font-sans`}>  
      <div className="h-full w-full bg-[#F2F2F7] dark:bg-[#000000] text-slate-900 dark:text-white relative transition-colors duration-700">  
          
        {/* iOS 科技感背景裝飾 - 增強光影質感 */}  
        <div className="absolute inset-0 pointer-events-none overflow-hidden">  
          <div className="absolute top-[-20%] left-[-10%] w-[70%] h-[70%] bg-blue-400/20 dark:bg-blue-600/10 rounded-full blur-[160px] animate-pulse duration-[10000ms]" />  
          <div className="absolute bottom-[-20%] right-[-10%] w-[70%] h-[70%] bg-purple-400/20 dark:bg-purple-600/10 rounded-full blur-[160px] animate-pulse duration-[12000ms]" />  
          <div className="absolute top-[40%] left-[40%] w-[40%] h-[40%] bg-emerald-400/10 dark:bg-emerald-600/5 rounded-full blur-[140px] animate-pulse duration-[15000ms]" />
        </div>  
  
        {/* 頂部狀態欄 (iOS Style) - 增加磨砂質感 */}  
        <div className="h-10 w-full bg-white/60 dark:bg-black/40 backdrop-blur-xl px-4 md:px-6 flex justify-between items-center text-[11px] font-medium z-50 border-b border-white/20 dark:border-white/5 shadow-sm">  
          <div className="flex items-center gap-3 md:gap-6">  
            <span className="text-slate-950 dark:text-white tracking-tight text-sm font-bold flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
              <span className="inline">{t('app')}</span>
            </span>  
            <div className="hidden sm:flex items-center gap-2 px-3 py-1 rounded-full bg-black/5 dark:bg-white/10 backdrop-blur-md">
              <Cpu className="w-3.5 h-3.5 opacity-70" /> 
              <span className="font-mono font-bold">12%</span>
            </div>  
            <div className="hidden md:flex items-center gap-2 px-3 py-1 rounded-full bg-black/5 dark:bg-white/10 backdrop-blur-md">
              <Database className="w-3.5 h-3.5 text-emerald-500" /> 
              <span className="font-bold">PostgreSQL</span>
              <span className="text-[9px] uppercase opacity-60 ml-1">{t('online')}</span>
            </div>  
          </div>  
          <div className="flex items-center gap-2 md:gap-4">  
            <button 
              onClick={() => setShowLangMenu(!showLangMenu)} 
              className="flex items-center gap-2 hover:bg-black/5 dark:hover:bg-white/10 px-2 md:px-3 py-1.5 rounded-full transition-all active:scale-95"
            >  
              <Globe className="w-3.5 h-3.5" /> 
              <span className="font-bold inline">{translations[lang].name}</span>
            </button>  
            <button 
              onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
              className="p-2 rounded-full hover:bg-black/5 dark:hover:bg-white/10 transition-all active:scale-95 active:rotate-12"
            >  
              {theme === 'light' ? <Moon className="w-4 h-4 text-slate-700" /> : <Sun className="w-4 h-4 text-yellow-400" />}  
            </button>  
            <span className="font-mono font-bold opacity-60 tabular-nums tracking-widest text-[10px] md:text-[11px]">
              {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>  
          </div>  
        </div>  
  
        {/* 語言選擇菜單 - iOS 彈出風格 */}  
        {showLangMenu && (  
          <>
            <div className="fixed inset-0 z-[90]" onClick={() => setShowLangMenu(false)} />
            <div className="absolute top-14 right-6 w-56 bg-white/80 dark:bg-[#1C1C1E]/80 backdrop-blur-2xl rounded-2xl shadow-2xl border border-white/20 dark:border-white/10 p-2 z-[100] animate-in fade-in zoom-in-95 duration-200 origin-top-right">  
              <div className="px-3 py-2 text-[10px] font-bold uppercase opacity-40 tracking-widest mb-1">Select Language</div>
              <div className="max-h-[300px] overflow-y-auto custom-scrollbar">
                {Object.keys(translations).map(code => (  
                  <button   
                    key={code}  
                    onClick={() => { setLang(code); setShowLangMenu(false); }}  
                    className={`w-full text-left px-3 py-2.5 rounded-xl text-xs transition-all flex justify-between items-center mb-1 ${lang === code ? 'bg-blue-500 text-white font-bold shadow-lg shadow-blue-500/30' : 'hover:bg-black/5 dark:hover:bg-white/10 text-slate-700 dark:text-slate-200'}`}  
                  >  
                    {translations[code].name}  
                    {lang === code && <Check className="w-3.5 h-3.5" />}  
                  </button>  
                ))}  
              </div>
            </div>  
          </>
        )}  
  
        {/* 桌面圖示區域 - 網格佈局優化 */}  
        <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-8 gap-6 md:gap-10 p-8 md:p-16 h-[calc(100%-140px)] content-start overflow-y-auto custom-scrollbar">  
          {appIcons.map(app => (  
            <div   
              key={app.id}   
              onClick={() => {
                // On mobile, single click might be better, but let's keep double click for desktop feel
                // and add a fallback for touch
                if (window.innerWidth < 768) toggleWindow(app.id);
              }}
              onDoubleClick={() => toggleWindow(app.id)}  
              className="flex flex-col items-center gap-2 md:gap-3 w-full cursor-pointer group"  
            >  
              <div className={`
                ${app.color} w-16 h-16 md:w-20 md:h-20 rounded-[20px] md:rounded-[24px] shadow-xl 
                group-hover:scale-105 group-active:scale-95 transition-all duration-300 
                flex items-center justify-center relative overflow-hidden
                ring-1 ring-black/5 dark:ring-white/10
              `}>  
                <div className="text-white w-8 h-8 md:w-10 md:h-10 drop-shadow-md flex items-center justify-center">
                  {app.iconUrl ? (
                    <img src={app.iconUrl} alt={app.name} className="w-full h-full object-cover rounded-lg" referrerPolicy="no-referrer" />
                  ) : (
                    app.icon
                  )}
                </div>
                
                {/* 凝膠光澤效果 */}
                <div className="absolute top-0 left-0 right-0 h-1/2 bg-gradient-to-b from-white/20 to-transparent pointer-events-none" />
                <div className="absolute inset-0 bg-gradient-to-tr from-black/10 to-transparent pointer-events-none" />
              </div>  
              <span className="text-[10px] md:text-xs font-medium text-slate-600 dark:text-slate-300 text-center drop-shadow-sm bg-white/30 dark:bg-black/30 backdrop-blur-md px-2 md:px-3 py-0.5 md:py-1 rounded-full border border-white/20 dark:border-white/5 truncate w-full">
                {app.name}
              </span>  
            </div>  
          ))}  
        </div>  
  
        {/* 視窗管理系統 */}  
        {openWindows.map(win => (  
          <WindowFrame   
            key={win.id}   
            win={win}   
            active={activeWin === win.id}  
            onFocus={() => setActiveWin(win.id)}  
            onClose={() => setOpenWindowIds(openWindowIds.filter(id => id !== win.id))}  
            theme={theme}  
            >  
            {win.id === 'connect' && <HostSettingsView config={config} setConfig={setConfig} t={t} isConnected={isConnected} setIsConnected={setIsConnected} />}  
            {win.id === 'devices' && <DeviceView sensors={sensors} getLabel={getLabel} t={t} />}  
            {win.id === 'store' && (
              <StoreView
                t={t}
                items={storeItems}
                installedAppIds={installedAppIds}
                onInstall={installApp}
                onOpen={toggleWindow}
              />
            )}  
            {win.id === 'studio' && <AppStudioView t={t} onAddApp={(newApp) => setCustomApps([...customApps, newApp])} />}
            {win.kind === 'embedded' && win.launchUrl && (
              <EmbeddedAppView
                appName={win.name}
                launchUrl={win.launchUrl}
                t={t}
              />
            )}
          </WindowFrame>  
        ))}  
  
        {/* 底部 Dock (iOS Style) - 懸浮玻璃質感 */}  
        <div className="absolute bottom-4 md:bottom-8 left-1/2 -translate-x-1/2 px-3 md:px-5 py-2 md:py-4 bg-white/20 dark:bg-black/20 backdrop-blur-3xl border border-white/30 dark:border-white/10 rounded-[24px] md:rounded-[40px] shadow-2xl flex items-center gap-3 md:gap-6 z-50 hover:bg-white/30 dark:hover:bg-black/30 transition-colors duration-500">  
          {appIcons.map(app => (  
            <button   
              key={app.id}  
              onClick={() => toggleWindow(app.id)}  
              className={`
                w-12 h-12 md:w-16 md:h-16 rounded-[14px] md:rounded-[20px] ${app.color} text-white p-3 md:p-4 
                hover:scale-110 md:hover:-translate-y-4 active:scale-95 transition-all duration-300 ease-out
                shadow-lg shadow-black/10 flex items-center justify-center relative group
                ring-1 ring-black/5 dark:ring-white/10 overflow-hidden
              `}  
            >  
            <div className="relative z-10 w-full h-full drop-shadow-md flex items-center justify-center">
              {app.iconUrl ? (
                <img src={app.iconUrl} alt={app.name} className="w-full h-full object-cover rounded-md" referrerPolicy="no-referrer" />
              ) : (
                app.icon
              )}
            </div>
              
              {/* 凝膠光澤 */}
              <div className="absolute top-0 left-0 right-0 h-1/2 bg-gradient-to-b from-white/25 to-transparent pointer-events-none" />
              
              {openWindowIds.includes(app.id) && (  
                <div className="absolute -bottom-2 md:-bottom-3 w-1 h-1 md:w-1.5 md:h-1.5 bg-slate-800 dark:bg-white rounded-full shadow-lg" />  
              )}  
            </button>  
          ))}  
        </div>  
      </div>  
    </div>  
  );  
}  
  
// --- 通用視窗容器 - 增強玻璃質感 ---  
const WindowFrame: React.FC<WindowProps> = ({ win, active, onFocus, onClose, theme, children }) => {  
  const isLargeWorkspace = win.id === 'connect' || win.kind === 'embedded';
  return (  
    <div   
      onClick={onFocus}  
      className={`
        absolute top-0 md:top-12 left-0 md:left-1/2 md:-translate-x-1/2 w-full ${isLargeWorkspace ? 'md:w-[calc(100%-48px)] md:h-[calc(100%-112px)]' : 'md:w-[900px] md:h-[600px]'} h-full md:rounded-[32px] shadow-2xl transition-all duration-500 flex flex-col overflow-hidden backdrop-blur-3xl 
        ${active ? 'z-40 scale-100 opacity-100 ring-1 ring-white/20 shadow-[0_25px_50px_-12px_rgba(0,0,0,0.25)]' : 'z-30 scale-95 opacity-60 border-transparent pointer-events-none blur-[1px] translate-y-4'} 
        ${theme === 'dark' ? 'bg-[#1C1C1E]/85 border-white/10' : 'bg-white/85 border-white/40'}
        border-0 md:border
      `}  
    >  
      {/* 視窗標題欄 */}
      <div className={`h-12 md:h-14 flex items-center justify-between px-4 md:px-6 select-none cursor-grab active:cursor-grabbing border-b ${theme === 'dark' ? 'border-white/5 bg-white/5' : 'border-black/5 bg-black/5'}`}>  
        <div className="flex gap-2.5 group">  
          <button onClick={(e) => {e.stopPropagation(); onClose();}} className="w-3.5 h-3.5 rounded-full bg-[#FF5F57] border border-[#E0443E] hover:brightness-90 transition-all shadow-sm flex items-center justify-center group-hover:text-black/50 text-transparent">
            <X className="w-2.5 h-2.5" strokeWidth={3} />
          </button>  
          <button className="hidden xs:block w-3.5 h-3.5 rounded-full bg-[#FEBC2E] border border-[#D89E24] hover:brightness-90 transition-all shadow-sm" />  
          <button className="hidden xs:block w-3.5 h-3.5 rounded-full bg-[#28C840] border border-[#1AAB29] hover:brightness-90 transition-all shadow-sm" />  
        </div>  
        <div className="flex flex-col items-center">
          <span className="text-[10px] md:text-xs font-bold opacity-70 uppercase tracking-widest flex items-center gap-2">
            {win.icon && <span className="w-3 h-3 opacity-50">{win.icon}</span>}
            {win.name}
          </span>  
        </div>
        <div className="w-14 flex justify-end">
          <div className="w-7 h-7 md:w-8 md:h-8 rounded-full bg-black/5 dark:bg-white/10 flex items-center justify-center">
            <User className="w-3.5 h-3.5 md:w-4 md:h-4 opacity-50" />
          </div>
        </div>  
      </div>  
      <div className="flex-1 overflow-hidden relative">
        {children}
        {/* 內容區域內陰影增強層次感 */}
        <div className="absolute inset-0 pointer-events-none shadow-[inset_0_10px_20px_-10px_rgba(0,0,0,0.05)]" />
      </div>  
    </div>  
  );  
}  
  
// --- 視窗：設備目錄 (Nickname 優先邏輯) - 優化列表設計 ---  
function DeviceView({ sensors, getLabel, t }: DeviceViewProps) {  
  return (  
    <div className="p-4 md:p-8 h-full flex flex-col gap-4 md:gap-6 bg-gradient-to-b from-transparent to-black/5 dark:to-white/5">  
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-end px-2 gap-4">  
        <div className="animate-in slide-in-from-left duration-500">  
          <h2 className="text-2xl md:text-3xl font-black tracking-tight mb-1">{t('devices')}</h2>  
          <span className="text-[10px] font-bold text-blue-500 uppercase tracking-[0.2em] bg-blue-500/10 px-2 py-1 rounded-md">{t('nickname')}</span>  
        </div>  
        <div className="relative animate-in slide-in-from-right duration-500 w-full sm:w-auto">  
          <Search className="absolute left-3 top-2.5 w-4 h-4 opacity-40" />  
          <input 
            type="text" 
            placeholder={t('search')} 
            className="pl-10 pr-6 py-2.5 bg-white/60 dark:bg-white/10 rounded-full text-xs font-medium outline-none w-full sm:w-64 focus:ring-2 ring-blue-500/50 backdrop-blur-md shadow-sm transition-all" 
          />  
        </div>  
      </div>  
  
      <div className="flex-1 overflow-y-auto space-y-4 md:space-y-5 pr-1 md:pr-2 custom-scrollbar pb-6">  
        {sensors.map((c, idx) => (  
          <div 
            key={c.cuid} 
            className="bg-white/60 dark:bg-[#2C2C2E]/60 backdrop-blur-md rounded-[20px] md:rounded-[24px] border border-white/40 dark:border-white/5 overflow-hidden shadow-sm hover:shadow-md transition-all duration-300 animate-in slide-in-from-bottom"
            style={{ animationDelay: `${idx * 100}ms` }}
          >  
            <div className="px-4 md:px-6 py-3 md:py-4 flex items-center justify-between bg-gradient-to-r from-slate-50/80 to-slate-100/50 dark:from-white/10 dark:to-white/5 border-b border-black/5 dark:border-white/5">  
              <div className="flex items-center gap-3">  
                <div className="w-7 h-7 md:w-8 md:h-8 rounded-full bg-amber-500/10 flex items-center justify-center">
                  <Zap className="w-3.5 h-3.5 md:w-4 md:h-4 text-amber-500" />  
                </div>
                <div>
                  <span className="text-xs md:text-sm font-black tracking-tight block">{getLabel(c)}</span>  
                  <span className="text-[8px] md:text-[9px] opacity-40 font-mono tracking-widest uppercase">{c.cuid}</span>  
                </div>
              </div>  
              <div className="flex gap-1.5">  
                 {[1,2,3].map(i => <div key={i} className="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)] animate-pulse" style={{ animationDelay: `${i * 200}ms` }} />)}  
              </div>  
            </div>  
            <div className="divide-y divide-black/5 dark:divide-white/5">  
              {c.sensors.map((s, sIdx) => (  
                <div key={s.suid} className="flex justify-between items-center p-3 md:p-4 pl-4 md:pl-6 hover:bg-blue-500/5 dark:hover:bg-white/5 transition-all group cursor-pointer">  
                  <div className="flex items-center gap-3 md:gap-4">
                    <div className="w-1 h-6 md:h-8 rounded-full bg-slate-200 dark:bg-white/10 group-hover:bg-blue-500 transition-colors" />
                    <div className="flex flex-col">  
                      <span className="text-xs md:text-sm font-bold text-slate-700 dark:text-slate-200 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">{getLabel(s)}</span>  
                      <span className="text-[8px] md:text-[9px] opacity-40 font-mono uppercase tracking-tighter">SUID: {s.suid}</span>  
                    </div>  
                  </div>
                  <div className="flex items-center gap-4 md:gap-6 pr-2 md:pr-4">  
                    <div className="text-right">  
                      <div className="text-base md:text-lg font-black text-slate-800 dark:text-white font-mono leading-none flex items-baseline justify-end gap-1">
                        {s.value}
                        <span className="text-[8px] md:text-[9px] opacity-40 font-bold uppercase">{s.unit}</span>  
                      </div>  
                    </div>  
                    <div className="w-7 h-7 md:w-8 md:h-8 rounded-full bg-slate-100 dark:bg-white/5 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all transform translate-x-2 group-hover:translate-x-0">
                      <ChevronRight className="w-3.5 h-3.5 md:w-4 md:h-4 opacity-50" />  
                    </div>
                  </div>  
                </div>  
              ))}  
            </div>  
          </div>  
        ))}  
      </div>  
    </div>  
  );  
}  
  
// --- 視窗：應用商店 (L2/L3 模式) - 優化卡片展示 ---  
function StoreView({ t, items, installedAppIds, onInstall, onOpen }: StoreViewProps) {  
  return (  
    <div className="p-6 md:p-10 flex flex-col gap-6 md:gap-8 h-full bg-gradient-to-tr from-transparent to-blue-500/5 overflow-y-auto custom-scrollbar">  
      <div className="animate-in slide-in-from-left duration-500">
        <h2 className="text-2xl md:text-3xl font-black tracking-tight mb-2">{t('store')}</h2>  
        <p className="text-[10px] md:text-xs opacity-50 font-medium">{t('storeIntro')}</p>
      </div>
  
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 md:gap-8">  
        {items.map((item, idx) => (  
          <div 
            key={item.id} 
            className="bg-white/60 dark:bg-[#2C2C2E]/60 backdrop-blur-xl p-6 md:p-8 rounded-[28px] md:rounded-[32px] border border-white/40 dark:border-white/5 hover:border-blue-500/30 transition-all duration-300 group relative overflow-hidden flex flex-col min-h-[280px] md:h-80 shadow-lg hover:shadow-2xl hover:-translate-y-1 animate-in zoom-in-95"
            style={{ animationDelay: `${idx * 150}ms` }}
          >  
            {/* 裝飾背景 */}
              <div className={`absolute -right-10 -top-10 w-32 h-32 rounded-full blur-3xl opacity-0 group-hover:opacity-20 transition-opacity duration-500 ${item.type === 'py' ? 'bg-blue-500' : item.type === 'app' ? 'bg-cyan-500' : 'bg-purple-500'}`} />
              
              <div className="flex justify-between items-start mb-4 md:mb-6 relative z-10">  
                <span className={`
                  px-3 md:px-4 py-1 md:py-1.5 rounded-full text-[9px] md:text-[10px] font-black uppercase tracking-widest shadow-sm border border-white/10
                  ${item.type === 'py' ? 'bg-blue-500/10 text-blue-600 dark:text-blue-400' : item.type === 'app' ? 'bg-cyan-500/10 text-cyan-600 dark:text-cyan-400' : 'bg-purple-500/10 text-purple-600 dark:text-purple-400'}
                `}>  
                  {item.type === 'py' ? t('pythonApp') : item.type === 'app' ? t('hostedApp') : t('skill')}  
                </span>  
                <div className="p-1.5 md:p-2 rounded-full bg-emerald-500/10 text-emerald-500">
                  <ShieldCheck className="w-4 h-4 md:w-5 md:h-5" />  
                </div>
              </div>  
              
              <h3 className="text-xl md:text-2xl font-black mb-2 md:mb-3 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">{item.name}</h3>  
              <p className="text-[10px] md:text-xs opacity-60 leading-relaxed flex-1 line-clamp-3 font-medium">{item.description}</p>  
              
              <button
                type="button"
                onClick={() => {
                  if (installedAppIds.includes(item.id)) {
                    onOpen(item.id);
                    return;
                  }
                  onInstall(item.id);
                }}
                className="w-full py-3 md:py-4 mt-4 bg-slate-900 dark:bg-white dark:text-slate-900 text-white rounded-2xl text-[10px] md:text-xs font-black uppercase tracking-widest shadow-xl active:scale-95 transition-all flex items-center justify-center gap-2 relative overflow-hidden group/btn"
              >  
                <div className="absolute inset-0 bg-white/20 translate-y-full group-hover/btn:translate-y-0 transition-transform duration-300" />
                {installedAppIds.includes(item.id) ? (
                  <>
                    <Activity className="w-3.5 h-3.5 md:w-4 md:h-4" /> {t('openApp')}
                  </>
                ) : (
                  <>
                    <Download className="w-3.5 h-3.5 md:w-4 md:h-4" /> {t('install')}
                  </>
                )}
              </button>  
            </div>  
          ))}  
        </div>  
      </div>  
    );  
  }  

function EmbeddedAppView({
  appName,
  launchUrl,
  t,
}: {
  appName: string;
  launchUrl: string;
  t: (key: string) => string;
}) {
  return (
    <div className="h-full bg-gradient-to-br from-transparent to-blue-500/5 p-4 md:p-6 flex flex-col gap-4">
      <div className="flex items-center justify-between gap-4 rounded-[24px] bg-white/60 dark:bg-white/5 border border-white/40 dark:border-white/10 px-5 py-4 backdrop-blur-xl shadow-sm">
        <div className="flex flex-col gap-1">
          <h2 className="text-lg md:text-xl font-black tracking-tight">{appName}</h2>
          <p className="text-[10px] md:text-xs opacity-60 font-medium">
            {t('embeddedHint')}
          </p>
        </div>
        <a
          href={launchUrl}
          target="_blank"
          rel="noreferrer"
          className="px-4 py-2 rounded-2xl bg-slate-900 dark:bg-white dark:text-slate-900 text-white text-[10px] md:text-xs font-black uppercase tracking-widest shadow-lg hover:opacity-90 transition-opacity"
        >
          {t('openInNewWindow')}
        </a>
      </div>
      <div className="flex-1 overflow-hidden rounded-[28px] border border-white/40 dark:border-white/10 bg-white/70 dark:bg-black/20 backdrop-blur-xl shadow-xl">
        <iframe
          title={appName}
          src={launchUrl}
          className="h-full w-full border-0 bg-white"
        />
      </div>
    </div>
  );
}

// --- 視窗：應用工作室 (AI 自動生成) ---
function AppStudioView({ t, onAddApp }: AppStudioViewProps) {
  const [appName, setAppName] = useState('');
  const [appDesc, setAppDesc] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [previewIcon, setPreviewIcon] = useState<string | null>(null);
  const [previewFeature, setPreviewFeature] = useState<string | null>(null);
  const [status, setStatus] = useState('');

  const generateApp = async () => {
    if (!appName) return;
    setIsGenerating(true);
    setStatus(t('studioGeneratingConcept'));
    
    try {
      const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });
      
      // 1. 生成圖示
      setStatus(t('studioGeneratingIcon'));
      const iconResponse = await ai.models.generateContent({
        model: 'gemini-2.5-flash-image',
        contents: {
          parts: [{ text: `A high-quality, modern, minimalist iOS style app icon for an application named "${appName}". Description: ${appDesc}. The icon should have vibrant colors, soft shadows, and a clean technological feel. No text in the icon.` }]
        },
        config: {
          imageConfig: { aspectRatio: "1:1" }
        }
      });

      let iconUrl = '';
      for (const part of iconResponse.candidates?.[0]?.content?.parts || []) {
        if (part.inlineData) {
          iconUrl = `data:image/png;base64,${part.inlineData.data}`;
          setPreviewIcon(iconUrl);
        }
      }

      // 2. 智慧配圖 (Feature Image)
      setStatus(t('studioGeneratingFeature'));
      const featureResponse = await ai.models.generateContent({
        model: 'gemini-2.5-flash-image',
        contents: {
          parts: [{ text: `A cinematic, high-resolution feature background image for an AI sensory application named "${appName}". Theme: ${appDesc}. Style: futuristic, clean, digital nervous system, abstract technology.` }]
        },
        config: {
          imageConfig: { aspectRatio: "16:9" }
        }
      });

      let featureUrl = '';
      for (const part of featureResponse.candidates?.[0]?.content?.parts || []) {
        if (part.inlineData) {
          featureUrl = `data:image/png;base64,${part.inlineData.data}`;
          setPreviewFeature(featureUrl);
        }
      }

      setStatus(t('studioGenerateDone'));
      
      const newApp: AppWindow = {
        id: `app_${Date.now()}`,
        name: appName,
        iconUrl: iconUrl,
        color: 'bg-gradient-to-br from-blue-500 to-purple-600',
        description: appDesc
      };

      onAddApp(newApp);
      setAppName('');
      setAppDesc('');
      
    } catch (error) {
      console.error('Generation failed:', error);
      setStatus(t('studioGenerateFailed'));
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="p-6 md:p-10 flex flex-col gap-8 h-full bg-gradient-to-br from-indigo-500/5 to-purple-500/5 overflow-y-auto custom-scrollbar">
      <div className="animate-in slide-in-from-left duration-500">
        <h2 className="text-2xl md:text-3xl font-black tracking-tight mb-2 flex items-center gap-3">
          <Sparkles className="text-indigo-500" />
          {t('appStudio')} <span className="text-sm font-bold opacity-40 uppercase tracking-widest">{t('aiCreator')}</span>
        </h2>
        <p className="text-[10px] md:text-xs opacity-50 font-medium">{t('studioIntro')}</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div className="space-y-6 animate-in slide-in-from-bottom duration-700">
          <div className="bg-white/50 dark:bg-black/20 p-6 rounded-[32px] border border-white/40 dark:border-white/5 shadow-xl space-y-6">
            <div>
              <label className="text-[10px] font-black uppercase opacity-40 ml-1 mb-2 block tracking-wider">{t('studioAppName')}</label>
              <input 
                type="text" 
                value={appName}
                onChange={e => setAppName(e.target.value)}
                placeholder={t('studioAppNamePlaceholder')}
                className="w-full bg-white/80 dark:bg-black/40 border-none rounded-2xl px-4 py-4 text-sm font-bold focus:ring-2 ring-indigo-500/50 transition-all shadow-inner"
              />
            </div>
            <div>
              <label className="text-[10px] font-black uppercase opacity-40 ml-1 mb-2 block tracking-wider">{t('studioDescription')}</label>
              <textarea 
                value={appDesc}
                onChange={e => setAppDesc(e.target.value)}
                placeholder={t('studioDescriptionPlaceholder')}
                rows={4}
                className="w-full bg-white/80 dark:bg-black/40 border-none rounded-2xl px-4 py-4 text-sm font-medium focus:ring-2 ring-indigo-500/50 transition-all shadow-inner resize-none"
              />
            </div>
            <button 
              onClick={generateApp}
              disabled={isGenerating || !appName}
              className={`
                w-full py-4 rounded-2xl text-xs font-black uppercase tracking-widest shadow-lg active:scale-95 transition-all flex items-center justify-center gap-3
                ${isGenerating ? 'bg-slate-200 dark:bg-white/10 text-slate-400' : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-indigo-500/30'}
              `}
            >
              {isGenerating ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Wand2 className="w-4 h-4" />}
              {isGenerating ? t('studioGeneratingAction') : t('studioGenerateAction')}
            </button>
            {status && <p className="text-[10px] text-center font-bold text-indigo-500 animate-pulse">{status}</p>}
          </div>
        </div>

        <div className="space-y-6 animate-in slide-in-from-right duration-700">
          <div className="bg-white/50 dark:bg-black/20 p-6 rounded-[32px] border border-white/40 dark:border-white/5 shadow-xl h-full flex flex-col gap-6">
            <h3 className="text-[10px] font-black uppercase opacity-40 tracking-widest">{t('studioPreview')}</h3>
            
            <div className="flex-1 flex flex-col gap-6">
              <div className="flex items-center gap-6">
                <div className="w-24 h-24 md:w-32 md:h-32 rounded-[28px] bg-slate-100 dark:bg-white/5 border border-white/20 flex items-center justify-center overflow-hidden shadow-inner relative group">
                  {previewIcon ? (
                    <img src={previewIcon} alt={t('iconPreview')} className="w-full h-full object-cover" />
                  ) : (
                    <ImageIcon className="w-8 h-8 opacity-20" />
                  )}
                  <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                    <span className="text-[8px] text-white font-bold uppercase tracking-widest">{t('iconPreview')}</span>
                  </div>
                </div>
                <div className="flex-1 space-y-2">
                  <div className="h-4 w-32 bg-slate-200 dark:bg-white/10 rounded-full animate-pulse" />
                  <div className="h-3 w-full bg-slate-100 dark:bg-white/5 rounded-full animate-pulse" />
                  <div className="h-3 w-2/3 bg-slate-100 dark:bg-white/5 rounded-full animate-pulse" />
                </div>
              </div>

              <div className="aspect-video w-full rounded-[24px] bg-slate-100 dark:bg-white/5 border border-white/20 flex items-center justify-center overflow-hidden shadow-inner relative group">
                {previewFeature ? (
                  <img src={previewFeature} alt={t('featurePreview')} className="w-full h-full object-cover" />
                ) : (
                  <ImageIcon className="w-12 h-12 opacity-20" />
                )}
                <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                  <span className="text-[10px] text-white font-bold uppercase tracking-widest">{t('featurePreview')}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
