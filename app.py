#!/usr/bin/env python3

import pathlib

import pandas as pd
import dash
import dash_core_components as dcc
import dash_html_components as html
import dash_table as dt
import plotly.graph_objs as go
from dash_dangerously_set_inner_html import DangerouslySetInnerHTML
from plotly.subplots import make_subplots

HERE = pathlib.Path(__file__).resolve().parent
datafile = HERE / "data.csv"

app = dash.Dash(
    __name__,
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)
app.title = "新型冠状病毒肺炎疫情历史数据"
server = app.server


def category_scatter(df, category, color, stacked=False):
    return go.Scatter(
        x=df[category].index,
        y=df[category],
        line=dict(color=color),
        mode="lines+markers",
        name=category,
        stackgroup="one" if stacked else None,
    )


def category_bar(df, category, color):
    return go.Bar(
        x=df[category].index,
        y=df[category],
        marker_color=color,
        opacity=0.25,
        name=category,
    )


def plot_categories(
    df, categories, colors, stacked=False, overlay_category=None, overlay_color=None
):
    scatter_data = [
        category_scatter(df, category, color, stacked=stacked)
        for category, color in zip(categories, colors)
    ]
    if not overlay_category:
        fig = go.Figure(data=scatter_data)
    else:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        for data in scatter_data:
            fig.add_trace(data, secondary_y=False)
        fig.add_trace(
            category_bar(df, overlay_category, overlay_color), secondary_y=True
        )
    fig.update_layout(
        plot_bgcolor="white",
        legend=dict(x=0, y=1),
        margin=go.layout.Margin(l=20, r=20, b=40, t=40, pad=0),
        hovermode="x",
        bargap=0.4,
    )
    axes_common_args = dict(
        fixedrange=True, linecolor="rgb(192, 192, 192)", gridcolor="rgb(230, 230, 230)"
    )
    fig.update_xaxes(tickformat="%m-%d", **axes_common_args)
    yaxes_common_args = dict(rangemode="tozero", **axes_common_args)
    if not overlay_category:
        fig.update_yaxes(**yaxes_common_args)
    else:
        fig.update_yaxes(**yaxes_common_args, secondary_y=False)
        fig.update_yaxes(**yaxes_common_args, tickformat=".1%", secondary_y=True)
        fig.update_yaxes(gridcolor="white", secondary_y=True)
    return fig


def setup():
    df = pd.read_csv(datafile, index_col=0, parse_dates=[0])
    df_display = df.rename(index=lambda d: d.strftime("%m-%d"))[::-1]

    df["重症比例"] = df["当前重症"] / df["当前确诊"]

    confirmed_color = "#f06061"
    severe_color = "#8c0d0d"
    suspected_color = "#ffd661"
    cured_color = "#65b379"
    death_color = "#87878b"
    other_color1 = "#cc00ff"
    other_color2 = "#3399ff"
    other_color3 = "#9900ff"

    figs = [
        (
            "确诊、重症及其比例、疑似走势",
            plot_categories(
                df,
                ["累计确诊", "当前确诊", "当前重症", "当前疑似"],
                [confirmed_color, other_color1, severe_color, suspected_color],
                overlay_category="重症比例",
                overlay_color=severe_color,
            ),
        ),
        (
            "确诊加疑似走势",
            plot_categories(
                df, ["累计确诊", "当前疑似"], [confirmed_color, suspected_color], stacked=True
            ),
        ),
        ("治愈、死亡走势", plot_categories(df, ["治愈", "死亡"], [cured_color, death_color])),
        (
            "每日新确诊、重症、疑似走势",
            plot_categories(
                df,
                ["新确诊", "新重症", "新疑似"],
                [confirmed_color, severe_color, suspected_color],
            ),
        ),
        ("每日新治愈、死亡走势", plot_categories(df, ["新治愈", "新死亡"], [cured_color, death_color])),
        (
            "追踪、观察走势",
            plot_categories(df, ["累计追踪", "当前观察"], [other_color2, other_color3]),
        ),
    ]

    app.layout = html.Div(
        children=[
            html.H1(children="新型冠状病毒肺炎疫情历史数据"),
            DangerouslySetInnerHTML(
                """<p class="app-note app-note--center">全部数据来自<a href="http://www.nhc.gov.cn/yjb/pqt/new_list.shtml" target="_blank">国家卫生健康委员会卫生应急办公室网站</a></p>
                <p class="app-note app-note--center">更多数据：<a href="https://news.qq.com/zt2020/page/feiyan.htm" target="_blank">腾讯新闻疫情实时追踪<a></p>"""
            ),
            dt.DataTable(
                columns=[{"name": "", "id": "category"}]
                + [{"name": date, "id": date} for date in df_display.index],
                data=[
                    {"category": series.name, **series.to_dict()}
                    for series in df_display.to_dict("series").values()
                ],
                id="table",
                style_table={"overflowX": "scroll"},
                style_header={
                    "backgroundColor": "rgb(230, 230, 230)",
                    "fontWeight": "bold",
                },
                style_cell_conditional=[
                    {"if": {"column_id": "category"}, "textAlign": "center"}
                ],
                style_data_conditional=[
                    {
                        "if": {"row_index": "odd"},
                        "backgroundColor": "rgb(248, 248, 248)",
                    }
                ],
            ),
            DangerouslySetInnerHTML("""<p class="app-note">注1：2月6日前卫健委未直接发布“当前确诊”数据，表中数据系通过“当前确诊=累计确诊&minus;治愈&minus;死亡”计算补充。该计算方法与2月6日起卫健委直接发布的数据相符。</p>"""),
            dcc.Tabs(
                [
                    dcc.Tab(
                        label=label,
                        children=[
                            dcc.Graph(
                                figure=fig,
                                config={
                                    "displaylogo": False,
                                    "modeBarButtonsToRemove": [
                                        "pan2d",
                                        "lasso2d",
                                        "toggleSpikelines",
                                    ],
                                },
                            )
                        ],
                        className="app-tab",
                        selected_className="app-tab--selected",
                    )
                    for label, fig in figs
                ],
                id="plot-tabs",
                className="app-tabs-container",
            ),
        ],
        className="app-container",
    )


setup()


def main():
    app.run_server(host="0.0.0.0", debug=True)


if __name__ == "__main__":
    main()
