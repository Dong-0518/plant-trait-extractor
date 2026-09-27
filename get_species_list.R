#!/usr/bin/env Rscript
# -*- coding: utf-8 -*-
# 获取物种名录：输入科名或属名，返回该类群所有物种

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) {
  cat('{"error": "Please provide family/genus name"}\n')
  quit(status = 1)
}

taxon_name <- args[1]

# 加载包
suppressMessages(library(dplyr))
suppressMessages(library(rWCVP))
suppressMessages(library(jsonlite))

tryCatch({
  # 自动判断：先按属名查，不行再按科名查
  # 先试 genus
  checklist <- tryCatch({
    wcvp_checklist(taxon = taxon_name, taxon_rank = "genus", infraspecies = FALSE, hybrids = FALSE)
  }, error = function(e) {
    # 属名查不到，试科名
    wcvp_checklist(taxon = taxon_name, taxon_rank = "family", infraspecies = FALSE, hybrids = FALSE)
  })
  
  if (nrow(checklist) == 0) {
    cat(sprintf('{"species": [], "message": "No taxa found for %s"}\n', taxon_name))
    quit(status = 0)
  }
  
  # 提取物种学名（用accepted_name字段）
  species_names <- unique(checklist$accepted_name)
  species_names <- species_names[!is.na(species_names)]
  species_names <- species_names[species_names != ""]
  
  # 输出JSON
  result <- list(
    species = as.character(species_names),
    count = length(species_names),
    query = taxon_name
  )
  
  cat(toJSON(result, auto_unbox = TRUE))
  
}, error = function(e) {
  err_msg <- gsub('"', "'", e$message)
  cat(sprintf('{"error": "%s"}\n', err_msg))
  quit(status = 1)
})
