import textwrap
import platform
import pytest

from conan.tools.cmake import CMakeToolchain
from conans.test.assets.cmake import gen_cmakelists
from conans.test.assets.sources import gen_function_h, gen_function_cpp
from conans.test.functional.utils import check_vs_runtime, check_exe_run
from conans.test.utils.tools import TestClient


@pytest.fixture
def client():
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.cmake import CMake, CMakeToolchain

        class Library(ConanFile):
            name = "hello"
            version = "1.0"
            settings = 'os', 'arch', 'compiler', 'build_type'
            exports_sources = 'hello.h', '*.cpp', 'CMakeLists.txt'
            options = {'shared': [True, False]}
            default_options = {'shared': False}

            def generate(self):
                tc = CMakeToolchain(self, generator="Ninja")
                tc.generate()

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def package(self):
                cmake = CMake(self)
                cmake.install()
        """)

    test_client = TestClient(path_with_spaces=False)
    test_client.save({'conanfile.py': conanfile,
                      "CMakeLists.txt": gen_cmakelists(libsources=["hello.cpp"],
                                                       appsources=["main.cpp"]),
                      "hello.h": gen_function_h(name="hello"),
                      "hello.cpp": gen_function_cpp(name="hello", includes=["hello"]),
                      "main.cpp": gen_function_cpp(name="main", includes=["hello"],
                                                   calls=["hello"])})
    return test_client


@pytest.mark.skipif(platform.system() != "Linux", reason="Only Linux")
@pytest.mark.parametrize("build_type,shared", [("Release", False), ("Debug", True)])
@pytest.mark.tool_compiler
@pytest.mark.tool_ninja
def test_locally_build_linux(build_type, shared, client):
    """ Ninja build must proceed using default profile and cmake build (Linux)
    """
    client.run('install . -s os=Linux -s arch=x86_64 -s build_type={} -o hello:shared={}'
               .format(build_type, shared))
    client.run_command('cmake . -G"Ninja" -DCMAKE_TOOLCHAIN_FILE={}'
                       .format(CMakeToolchain.filename))

    client.run_command('ninja')
    if shared:
        assert "Linking CXX shared library libmylibrary.so" in client.out
    else:
        assert "Linking CXX static library libmylibrary.a" in client.out

    client.run_command("./myapp")
    check_exe_run(client.out, ["main", "hello"], "gcc", None, build_type, "x86_64", cppstd=None)


@pytest.mark.skipif(platform.system() != "Windows", reason="Only windows")
@pytest.mark.parametrize("build_type,shared", [("Release", False), ("Debug", True)])
@pytest.mark.tool_compiler
@pytest.mark.tool_ninja
def test_locally_build_msvc(build_type, shared, client):
    """ Ninja build must proceed using default profile and cmake build (Windows Release)
    """
    msvc_version = "15"
    client.run("install . -s build_type={} -o hello:shared={}".format(build_type, shared))

    client.run_command('conanvcvars.bat && cmake . -G "Ninja" '
                       '-DCMAKE_TOOLCHAIN_FILE=conan_toolchain.cmake '
                       '-DCMAKE_BUILD_TYPE={}'.format(build_type))

    client.run_command("conanvcvars.bat && ninja")

    libname = "mylibrary.dll" if shared else "mylibrary.lib"
    assert libname in client.out

    client.run_command("myapp.exe")
    # TODO: Need full msvc version check
    check_exe_run(client.out, ["main", "hello"], "msvc", "19", build_type, "x86_64", cppstd="14")
    check_vs_runtime("myapp.exe", client, msvc_version, build_type, architecture="amd64")
    check_vs_runtime(libname, client, msvc_version, build_type, architecture="amd64")

    # TODO: This functionality is missing
    # client.run("create . hello/0.1@")


@pytest.mark.skipif(platform.system() != "Windows", reason="Only windows")
@pytest.mark.parametrize("build_type,shared", [("Release", False), ("Debug", True)])
@pytest.mark.tool_mingw64
@pytest.mark.tool_compiler
@pytest.mark.tool_ninja
def test_locally_build_gcc(build_type, shared, client):
    """ Ninja build must proceed using default profile and cmake build (Windows Release)
    """
    # FIXME: Note the gcc version is still incorrect
    gcc = ("-s os=Windows -s compiler=gcc -s compiler.version=4.9 -s compiler.libcxx=libstdc++ "
           "-s arch=x86_64 -s build_type={}".format(build_type))

    client.run("install . {} -o hello:shared={}".format(gcc, shared))

    client.run_command('cmake . -G "Ninja" '
                       '-DCMAKE_TOOLCHAIN_FILE=conan_toolchain.cmake '
                       '-DCMAKE_BUILD_TYPE={}'.format(build_type))

    libname = "mylibrary.dll" if shared else "libmylibrary.a"
    client.run_command("ninja")
    assert libname in client.out

    client.run_command("myapp.exe")
    # TODO: Need full gcc version check
    check_exe_run(client.out, ["main", "hello"], "gcc", None, build_type, "x86_64", cppstd=None)


@pytest.mark.skipif(platform.system() != "Darwin", reason="Requires apple-clang")
@pytest.mark.parametrize("build_type,shared", [("Release", False), ("Debug", True)])
@pytest.mark.tool_compiler
@pytest.mark.tool_ninja
def test_locally_build_macos(build_type, shared, client):
    client.run('install . -s os=Macos -s arch=x86_64 -s build_type={} -o hello:shared={}'
               .format(build_type, shared))
    client.run_command('cmake . -G"Ninja" -DCMAKE_TOOLCHAIN_FILE={}'
                       .format(CMakeToolchain.filename))

    client.run_command('ninja')
    if shared:
        assert "Linking CXX shared library libmylibrary.dylib" in client.out
    else:
        assert "Linking CXX static library libmylibrary.a" in client.out

    command_str = 'DYLD_LIBRARY_PATH="%s" ./myapp' % client.current_folder
    client.run_command(command_str)
    check_exe_run(client.out, ["main", "hello"], "apple-clang", None, build_type, "x86_64",
                  cppstd=None)
