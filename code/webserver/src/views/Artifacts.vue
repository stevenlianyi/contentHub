<!-- ============================================================================
 * Artifacts · 产物台账（P-07，Step 12）
 * ----------------------------------------------------------------------------
 * 页面职责：只做页头与编排 —— 列表主体（筛选 / 两视图 / 分组折叠 / 分页 / 三态 / 预览抽屉 /
 *   重新渲染）全部收敛在 `views/artifacts/ArtifactsPanel.vue`（越界授权文件，裁定 L），
 *   以便与 P-03 Tab4 共用同一套列表（满足「单文件 ≤ 600 行」，§2.1）。
 *
 * 取数契约（后端事实，服从）：
 *   · `artifactqry` 为**免登录端点**（§2.9.8），出参信封为 **keep**：`data` 为数组，
 *     另带 `total / beginNum / endNum / indexKey`（P-ENV-01 §3.3）；
 *   · 服务端过滤能力（2026-09-22 手改 `funcArtifactQry`，附录 B R-28）已支持
 *     `jobID / topicID / kind / platform / artifactStatus / order` → 本页五类筛选**全部下发**，
 *     不存在「已加载页内筛选」兜底（裁定 A）。
 *
 * 直达落点（裁定 J，必须消费）：
 *   · `?jobID=<ch_render_job.recID>` —— Step 11「查看产物」的落点；
 *   · `?topicID=<ch_topic.recID>` —— Tab3 / Tab4 互跳；
 *   两者与视图（`?view=`）、页码（`?page=`）一并写入 URL，刷新与前进后退均保持。
 * ========================================================================== -->
<template>
  <section class="flex flex-col gap-lg">
    <header class="flex flex-col gap-xs">
      <h1 class="text-h1 text-ch-text-primary">产物台账</h1>
      <p class="text-body-s text-ch-text-secondary">
        渲染产物的缩略图 / 规格 / 类型与平台徽标 / 大小 / 版本 / 序号 / 状态 / 保留期；
        支持预览、下载，以及过期后的重新渲染（过期清理与归档由后端定时任务负责，本页不提供清理入口）。
      </p>
    </header>

    <!-- 列表主体：与服务端筛选 / 分页 / URL query 同步（`sync-query`） -->
    <ArtifactsPanel sync-query @empty-action="goTopics" />
  </section>
</template>

<script setup>
import { useRouter } from 'vue-router'
import ArtifactsPanel from '@/views/artifacts/ArtifactsPanel.vue'

const router = useRouter()

/** 无产物时的主操作：去主题库挑主题并发起渲染 */
function goTopics() {
  router.push('/topics')
}
</script>
