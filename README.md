<https://ncov.zhimingwang.org>

This is another 2019-nCoV epidemic stats gathering and visualization project. Stats are gathered by consuming daily reports from [National Health Commission](http://www.nhc.gov.cn/yjb/pqt/new_list.shtml).

Scraping is currently done semi-automatically with the help of [chrome-cli](https://github.com/prasmussen/chrome-cli). Unfortunately the NHC website employs strong anti-scraping measures that even the up-to-date [puppeteer-extra-plugin-stealth](https://github.com/berstend/puppeteer-extra/tree/master/packages/puppeteer-extra-plugin-stealth) cannot penetrate. In fact, even running puppeteer in non-headless mode and manually browsing the website leads to a 400 block immediately; I'm impressed but not amused.

The frontend is created using [Plotly Dash](https://plot.ly/dash/).

## Deployment

### Google App Engine

The site is currently deployed on GAE. Deployment:

```shell
make gcp && cd deploy/gcp && gcloud app deploy && cd ../..
```

### WSGI

`app.server` is compatible with any WSGI server, e.g. Gunicorn.
