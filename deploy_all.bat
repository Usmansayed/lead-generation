@echo off
echo Deploying LinkedIn...
cd services\apify-actors\linkedin-lead-scraper
call apify push
if %errorlevel% neq 0 exit /b %errorlevel%
cd ..\..\..

echo Deploying Twitter...
cd services\apify-actors\twitter-lead-scraper
call apify push
if %errorlevel% neq 0 exit /b %errorlevel%
cd ..\..\..

echo Deploying Quora...
cd services\apify-actors\quora-lead-scraper
call apify push
if %errorlevel% neq 0 exit /b %errorlevel%
cd ..\..\..

echo Deploying Upwork...
cd services\apify-actors\upwork-lead-scraper
call apify push
if %errorlevel% neq 0 exit /b %errorlevel%
cd ..\..\..

echo Deploying Craigslist...
cd services\apify-actors\craigslist-lead-scraper
call apify push
if %errorlevel% neq 0 exit /b %errorlevel%
cd ..\..\..

echo Deploying IndieHackers...
cd services\apify-actors\indiehackers-lead-scraper
call apify push
if %errorlevel% neq 0 exit /b %errorlevel%
cd ..\..\..

echo ALL DEPLOYMENTS SUCCESSFUL!
