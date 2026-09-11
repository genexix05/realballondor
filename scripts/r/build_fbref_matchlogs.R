#!/usr/bin/env Rscript
# Build FBref player match-log CSV via worldfootballR
# Install once:
#   brew install r
#   Rscript -e 'install.packages("devtools"); devtools::install_github("JaseZiv/worldfootballR")'
#
# Usage:
#   Rscript scripts/r/build_fbref_matchlogs.R 2026 ESP 450
#
# Args: season_end_year country min_minutes

suppressPackageStartupMessages({
  library(worldfootballR)
  library(dplyr)
})

args <- commandArgs(trailingOnly = TRUE)
season_end_year <- as.integer(if (length(args) >= 1) args[[1]] else 2026)
country <- if (length(args) >= 2) args[[2]] else "ESP"
min_minutes <- as.numeric(if (length(args) >= 3) args[[3]] else 450)
time_pause <- 3

message("season_end_year=", season_end_year, " country=", country, " min_minutes=", min_minutes)

league_url <- fb_league_urls(
  country = country,
  gender = "M",
  season_end_year = season_end_year,
  tier = "1st"
)
message("league_url=", league_url)

team_urls <- fb_teams_urls(league_url)
message("teams=", length(team_urls))

player_urls <- unique(unlist(lapply(team_urls, function(u) {
  Sys.sleep(time_pause)
  fb_player_urls(u)
})))
message("players=", length(player_urls))

# Optional: filter via big5 advanced season stats if available
# For speed on BdO we still scrape all with minutes later via logs.

out_dir <- file.path("data", "raw", "fbref")
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)
partial <- file.path(out_dir, sprintf("player_match_logs_wfr_%s_%s.partial.csv", country, season_end_year))
final <- file.path(out_dir, sprintf("player_match_logs_wfr_%s_%s.csv", country, season_end_year))

all_logs <- list()
for (i in seq_along(player_urls)) {
  url <- player_urls[[i]]
  message(sprintf("[%d/%d] %s", i, length(player_urls), url))
  logs <- tryCatch(
    fb_player_match_logs(url, season_end_year = season_end_year, stat_type = "summary", time_pause = time_pause),
    error = function(e) {
      message("  fail: ", conditionMessage(e))
      NULL
    }
  )
  if (is.null(logs) || !nrow(logs)) next
  logs$player_url <- url
  all_logs[[length(all_logs) + 1]] <- logs
  dplyr::bind_rows(all_logs) |>
    readr::write_csv(partial)
}

df <- dplyr::bind_rows(all_logs)
readr::write_csv(df, final)
message("Wrote ", nrow(df), " rows -> ", final)
