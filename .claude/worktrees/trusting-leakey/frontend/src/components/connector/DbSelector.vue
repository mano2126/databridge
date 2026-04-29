<template>
  <div class="dbs-wrap">
    <div class="dbs-icon" :style="{background:meta.bg,color:meta.color}">{{ meta.label }}</div>
    <select :value="modelValue" @change="$emit('update:modelValue',$event.target.value)">
      <option v-for="d in list" :key="d.value" :value="d.value">{{ d.name }}</option>
    </select>
    <div class="chev"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="2,4 6,8 10,4"/></svg></div>
  </div>
</template>
<script setup>
import { computed } from 'vue'
import { DB_META, SOURCE_DBS, TARGET_DBS } from '@/constants/dbMeta.js'
const p = defineProps({ modelValue:{type:String,default:'mssql'}, mode:{type:String,default:'source'} })
defineEmits(['update:modelValue'])
const list = computed(() => p.mode==='source' ? SOURCE_DBS : TARGET_DBS)
const meta = computed(() => DB_META[p.modelValue] || {label:'??',bg:'#eee',color:'#333'})
</script>
<style scoped>
.dbs-wrap{position:relative}
select{width:100%;appearance:none;-webkit-appearance:none;background:var(--bg-secondary);border:0.5px solid var(--border-mid);border-radius:var(--radius-md);padding:8px 28px 8px 38px;font-size:12.5px;color:var(--text-primary);cursor:pointer;font-family:var(--font);transition:border-color .12s}
select:focus{outline:none;border-color:var(--accent-blue)}
.dbs-icon{position:absolute;left:9px;top:50%;transform:translateY(-50%);width:20px;height:20px;border-radius:4px;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700;pointer-events:none}
.chev{position:absolute;right:9px;top:50%;transform:translateY(-50%);pointer-events:none;color:var(--text-tertiary)}
.chev svg{width:11px;height:11px;display:block}
</style>
