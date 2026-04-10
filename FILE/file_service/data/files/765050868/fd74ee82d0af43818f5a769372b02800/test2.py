import os
import jpype
import jaydebeapi

def connect_openGauss_direct():
    try:
        # 先确保 JAVA_HOME（也可以写死到你的 JDK 目录）
        if "JAVA_HOME" not in os.environ:
            os.environ["JAVA_HOME"] = "/Library/Java/JavaVirtualMachines/temurin-8.jdk/Contents/Home"

        jvm_path = jpype.getDefaultJVMPath()  # 会用到 JAVA_HOME
        if not jpype.isJVMStarted():
            jpype.startJVM(jvm_path)

        jclassname = "org.opengauss.Driver"
        url = "jdbc:opengauss://10.221.2.166:5432/digiop_bark"
        username = "root"
        password = "123456"

        # ⚠️ 注意：你还需要 opengauss 的 JDBC 驱动 jar
        jars = ["/Users/justiy/Downloads/dws_euler_kunpeng_jdbc/jdbc/gsjdbc4.jar"]  # 改成真实路径

        conn = jaydebeapi.connect(
            jclassname=jclassname,
            url=url,
            driver_args=[username, password],
            jars=jars
        )
        print("数据库连接成功！")
        return conn

    except Exception as e:
        print(f"连接失败: {e}")
        return None

connect_openGauss_direct()

