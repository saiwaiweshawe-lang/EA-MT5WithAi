from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QStatusBar, QMenuBar, QMenu,
    QMessageBox, QLabel, QPushButton, QFrame
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QIcon


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("量化交易系统 v2.8")
        self.setMinimumSize(1200, 800)
        
        self.config_manager = None
        self.mt5_connector = None
        self.exchanges = {}
        self.strategy_engine = None
        self.smart_selector = None
        
        self._init_ui()
        self._init_menu()
        self._init_status_bar()
        
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._on_update)
        self.update_timer.start(5000)

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_dashboard_tab(), "仪表盘")
        self.tabs.addTab(self._create_mt5_tab(), "MT5")
        self.tabs.addTab(self._create_exchange_tab(), "交易所")
        self.tabs.addTab(self._create_news_tab(), "新闻")
        self.tabs.addTab(self._create_strategy_tab(), "策略")
        self.tabs.addTab(self._create_settings_tab(), "设置")
        
        main_layout.addWidget(self.tabs)

    def _create_dashboard_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        title = QLabel("系统状态总览")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        
        status_frame = QFrame()
        status_frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        status_layout = QVBoxLayout(status_frame)
        
        self.mt5_status_label = QLabel("MT5: 未连接")
        status_layout.addWidget(self.mt5_status_label)
        
        self.exchange_status_label = QLabel("交易所: 未连接")
        status_layout.addWidget(self.exchange_status_label)
        
        self.news_status_label = QLabel("新闻爬虫: 已停止")
        status_layout.addWidget(self.news_status_label)
        
        self.trading_status_label = QLabel("交易状态: 待机")
        status_layout.addWidget(self.trading_status_label)
        
        layout.addWidget(status_frame)
        
        self.recommendation_label = QLabel("推荐交易品种: --")
        self.recommendation_label.setStyleSheet("font-size: 14px; padding: 10px;")
        layout.addWidget(self.recommendation_label)
        
        layout.addStretch()
        
        return widget

    def _create_mt5_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        title = QLabel("MT5 连接管理")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)
        
        config_frame = QFrame()
        config_frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        config_layout = QVBoxLayout(config_frame)
        
        self.mt5_server_input = self._create_input_row("服务器:")
        config_layout.addLayout(self.mt5_server_input)
        
        self.mt5_account_input = self._create_input_row("账户:")
        config_layout.addLayout(self.mt5_account_input)
        
        self.mt5_password_input = self._create_input_row("密码:")
        config_layout.addLayout(self.mt5_password_input)
        
        btn_layout = QHBoxLayout()
        connect_btn = QPushButton("连接")
        connect_btn.clicked.connect(self._on_mt5_connect)
        disconnect_btn = QPushButton("断开")
        disconnect_btn.clicked.connect(self._on_mt5_disconnect)
        btn_layout.addWidget(connect_btn)
        btn_layout.addWidget(disconnect_btn)
        config_layout.addLayout(btn_layout)
        
        layout.addWidget(config_frame)
        
        symbols_label = QLabel("可用品种:")
        symbols_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(symbols_label)
        
        self.mt5_symbols_label = QLabel("未获取")
        layout.addWidget(self.mt5_symbols_label)
        
        layout.addStretch()
        
        return widget

    def _create_exchange_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        title = QLabel("交易所 API 管理")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)
        
        self.exchange_frames = {}
        for exchange_name in ["Binance", "OKX", "Bybit"]:
            frame = self._create_exchange_frame(exchange_name)
            self.exchange_frames[exchange_name] = frame
            layout.addWidget(frame)
        
        layout.addStretch()
        return widget

    def _create_exchange_frame(self, name: str) -> QFrame:
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        layout = QVBoxLayout(frame)
        
        title = QLabel(f"{name}")
        title.setStyleSheet("font-weight: bold;")
        layout.addWidget(title)
        
        api_key_input = self._create_input_row("API Key:")
        layout.addLayout(api_key_input)
        
        api_secret_input = self._create_input_row("API Secret:")
        layout.addLayout(api_secret_input)
        
        btn_layout = QHBoxLayout()
        connect_btn = QPushButton("连接")
        connect_btn.clicked.connect(lambda: self._on_exchange_connect(name))
        test_btn = QPushButton("测试")
        test_btn.clicked.connect(lambda: self._on_exchange_test(name))
        btn_layout.addWidget(connect_btn)
        btn_layout.addWidget(test_btn)
        layout.addLayout(btn_layout)
        
        status_label = QLabel("状态: 未连接")
        layout.addWidget(status_label)
        
        if not hasattr(self, 'exchange_status_labels'):
            self.exchange_status_labels = {}
        self.exchange_status_labels[name] = status_label
        
        return frame

    def _create_news_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        title = QLabel("新闻爬虫控制")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)
        
        control_frame = QFrame()
        control_frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        control_layout = QVBoxLayout(control_frame)
        
        btn_layout = QHBoxLayout()
        start_btn = QPushButton("开始爬取")
        start_btn.clicked.connect(self._on_news_start)
        stop_btn = QPushButton("停止爬取")
        stop_btn.clicked.connect(self._on_news_stop)
        refresh_btn = QPushButton("立即刷新")
        refresh_btn.clicked.connect(self._on_news_refresh)
        btn_layout.addWidget(start_btn)
        btn_layout.addWidget(stop_btn)
        btn_layout.addWidget(refresh_btn)
        control_layout.addLayout(btn_layout)
        
        layout.addWidget(control_frame)
        
        self.news_list_label = QLabel("最新新闻:\n暂无")
        layout.addWidget(self.news_list_label)
        
        layout.addStretch()
        return widget

    def _create_strategy_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        title = QLabel("量化策略")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)
        
        status_frame = QFrame()
        status_frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        status_layout = QVBoxLayout(status_frame)
        
        self.strategy_status_label = QLabel("策略状态: 未启动")
        status_layout.addWidget(self.strategy_status_label)
        
        self.strategy_performance_label = QLabel("性能: --")
        status_layout.addWidget(self.strategy_performance_label)
        
        layout.addWidget(status_frame)
        
        btn_layout = QHBoxLayout()
        start_btn = QPushButton("启动策略")
        start_btn.clicked.connect(self._on_strategy_start)
        stop_btn = QPushButton("停止策略")
        stop_btn.clicked.connect(self._on_strategy_stop)
        btn_layout.addWidget(start_btn)
        btn_layout.addWidget(stop_btn)
        layout.addLayout(btn_layout)
        
        self.signals_label = QLabel("当前信号:\n暂无")
        layout.addWidget(self.signals_label)
        
        layout.addStretch()
        return widget

    def _create_settings_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        title = QLabel("系统设置")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)
        
        auto_trade_frame = QFrame()
        auto_trade_layout = QVBoxLayout(auto_trade_frame)
        
        auto_trade_label = QLabel("自动交易:")
        auto_trade_layout.addWidget(auto_trade_label)
        
        btn_layout = QHBoxLayout()
        enable_btn = QPushButton("启用")
        enable_btn.clicked.connect(self._on_enable_auto_trade)
        disable_btn = QPushButton("禁用")
        disable_btn.clicked.connect(self._on_disable_auto_trade)
        btn_layout.addWidget(enable_btn)
        btn_layout.addWidget(disable_btn)
        auto_trade_layout.addLayout(btn_layout)
        
        layout.addWidget(auto_trade_frame)
        layout.addStretch()
        return widget

    def _create_input_row(self, label: str) -> QHBoxLayout:
        layout = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setMinimumWidth(100)
        layout.addWidget(lbl)
        
        from PyQt6.QtWidgets import QLineEdit
        input_field = QLineEdit()
        input_field.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(input_field)
        
        return layout

    def _init_menu(self):
        menubar = self.menuBar()
        
        file_menu = menubar.addMenu("文件")
        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        help_menu = menubar.addMenu("帮助")
        about_action = QAction("关于", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

    def _init_status_bar(self):
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("就绪")

    def _on_update(self):
        if self.mt5_connector and self.mt5_connector.is_connected():
            self.mt5_status_label.setText(f"MT5: 已连接 ({self.mt5_connector._account_info.server if self.mt5_connector._account_info else 'Unknown'})")
        
        for name, exchange in self.exchanges.items():
            if exchange.is_connected():
                self.exchange_status_labels[name].setText(f"状态: 已连接")

    def _on_mt5_connect(self):
        from ..connectors import MT5Connector
        self.mt5_connector = MT5Connector()
        
        server = self.mt5_server_input.itemAt(1).widget().text()
        account = int(self.mt5_account_input.itemAt(1).widget().text() or 0)
        password = self.mt5_password_input.itemAt(1).widget().text()
        
        success, msg = self.mt5_connector.connect(server, account, password)
        
        if success:
            self.mt5_status_label.setText(f"MT5: 已连接 ({self.mt5_connector._account_info.server if self.mt5_connector._account_info else server})")
            symbols = self.mt5_connector.get_available_symbols()
            self.mt5_symbols_label.setText(f"可用品种: {', '.join(symbols[:10])}...")
            self.statusBar.showMessage(msg)
        else:
            QMessageBox.warning(self, "连接失败", msg)

    def _on_mt5_disconnect(self):
        if self.mt5_connector:
            self.mt5_connector.disconnect()
            self.mt5_status_label.setText("MT5: 未连接")
            self.mt5_symbols_label.setText("未获取")
            self.statusBar.showMessage("MT5 已断开")

    def _on_exchange_connect(self, name: str):
        from ..connectors import create_exchange
        
        exchange = create_exchange(name)
        
        frame = self.exchange_frames[name]
        api_key = frame.layout().itemAt(1).layout().itemAt(1).widget().text()
        api_secret = frame.layout().itemAt(2).layout().itemAt(1).widget().text()
        
        success, msg = exchange.connect(api_key, api_secret)
        
        if success:
            self.exchanges[name] = exchange
            self.exchange_status_labels[name].setText(f"状态: 已连接")
            self.statusBar.showMessage(msg)
        else:
            QMessageBox.warning(self, "连接失败", msg)

    def _on_exchange_test(self, name: str):
        if name in self.exchanges:
            info = self.exchanges[name].get_account_info()
            if info:
                self.exchange_status_labels[name].setText(
                    f"状态: 已连接 | 余额: {info.balance:.2f}"
                )

    def _on_news_start(self):
        self.news_status_label.setText("新闻爬虫: 运行中")
        self.statusBar.showMessage("新闻爬虫已启动")

    def _on_news_stop(self):
        self.news_status_label.setText("新闻爬虫: 已停止")
        self.statusBar.showMessage("新闻爬虫已停止")

    def _on_news_refresh(self):
        self.news_list_label.setText("最新新闻:\n正在刷新...")
        self.statusBar.showMessage("正在获取新闻...")

    def _on_strategy_start(self):
        self.strategy_status_label.setText("策略状态: 运行中")
        self.statusBar.showMessage("量化策略已启动")

    def _on_strategy_stop(self):
        self.strategy_status_label.setText("策略状态: 已停止")
        self.statusBar.showMessage("量化策略已停止")

    def _on_enable_auto_trade(self):
        self.trading_status_label.setText("交易状态: 自动")
        self.statusBar.showMessage("自动交易已启用")

    def _on_disable_auto_trade(self):
        self.trading_status_label.setText("交易状态: 手动")
        self.statusBar.showMessage("自动交易已禁用")

    def _on_about(self):
        QMessageBox.about(
            self,
            "关于",
            "量化交易系统 v2.8\n\n"
            "开源量化交易客户端\n"
            "支持 MT5 / Binance / OKX / Bybit\n\n"
            "基于 PyQt6 构建"
        )

    def closeEvent(self, event):
        if self.mt5_connector:
            self.mt5_connector.disconnect()
        for exchange in self.exchanges.values():
            exchange.disconnect()
        event.accept()
