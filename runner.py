import os
import time
import random
import argparse
from collections import defaultdict
from prettytable import PrettyTable
from scipy.__config__ import show

import yaml
import traceback
import xerrors
import xerrors.cprint as cp
from xerrors.metrics import confidence_interval
from xerrors.utils import print_disk_space


# TODO
# Resume from checkpoint


def runner_parser():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-Y", action="store_true", help="Confirm to run")
    parser.add_argument("-T", "--test-mode", action="store_true", help="Run Test")
    parser.add_argument("--gpu", type=str, default="not specified")
    parser.add_argument("--output", type=str, default="/hdd/zwj/theta", help="Output directory")
    parser.add_argument("--debug", action="store_true", help="Debug mode")
    parser.add_argument("--offline", action="store_true", help="Wandb offline")

    args, _ = parser.parse_known_args()
    return args


class Runner(object):
    def __init__(self,
                 name="Runner",
                 run_id=None,
                 log_dir="output",
                 configuration_index=None,
                 block_configuration=None,
                 **kwargs):

        self.results = None
        self.name = name
        self.configuration_index = self._parse_index(configuration_index)
        self.block_configuration = block_configuration

        self.global_gpu = None

        self.args = runner_parser()
        self.list = []
        self.runner_list = []
        self.test_list = []

        # result
        self.result = {}

        # config dirs
        timer = xerrors.cur_time()
        self.run_id = run_id or f"RUN_{timer}"
        self.run_dir = os.path.join(log_dir, "runner", f"{timer.year}-{timer.mon}", f"{self.name}-{self.run_id}")
        os.makedirs(self.run_dir, exist_ok=True)

        # Temp
        self.special_content = {
            "seed": lambda k, v: f" SEED@{v}",
            "dataset_config": lambda k, v: f"-D{v.split('/')[-1].split('.')[0][-1:]}",
            "gpu": lambda k, v: f" GPU#{v}",
        }

        # skip
        self.skip_name_list = []
        self.success = False

    def run(self, func,
            gpu_id: str = "",
            before_train_hook: callable = None,
            main_index: str = None,
            **kwargs):

        gpu_id = gpu_id or self.modified_gpu()
        start_index = kwargs.get("start_index", 0)
        use_top_config = kwargs.get("use_top_config")
        if self.args.test_mode:
            self.list = self.test_list
        else:
            self.list = self.runner_list
            if before_train_hook:
                self.list = before_train_hook(self, self.list, gpu_id=gpu_id)

        job_list_count = len(self.list)
        if job_list_count == 0:
            cp.warning(self.name, "No configurations found")
            return

        print_disk_space()

        infos = []
        print(cp.yellow(f"\nRunning {self.name} with {job_list_count} configurations", bold=True))
        for ci, config in enumerate(self.list):
            config = self.refine_config(config)
            config["cid"] = ci
            config["run_id"] = self.run_id
            config["gpu"] = gpu_id  # 不使用 config 中指定的 gpu
            config["output"] = self.args.output
            config["debug"] = self.args.debug
            config["offline"] = self.args.offline

            show_name = self.get_show_name(config)

            if ci == start_index:
                info = cp.green(f"▶ {ci} {config['tag']}|T|{show_name}", bold=True)
            else:
                info = cp.blue(f"  {ci} {config['tag']}|T|{show_name}", bold=True)

            infos.append(info)

        print("\n".join(align_strings(infos)))

        # 确认，开始运行，输入y确认，其余取消
        if not self.args.debug and not self.args.Y:
            prompt = "Confirm to run ([y]/n)?: "
            if kwargs.get("skip_value"):
                prompt = f"Confirm to run with skip value {cp.yellow(kwargs.get('skip_value'), True)} ([y]/n)?: "

            option = input(prompt)

            try:
                float_option = float(option)
                assert 0 <= float_option < 1, "Wrong option!"
                kwargs["skip_value"] = float_option
                print(f"Skip value set to {cp.yellow(float_option, True)}")
            except (ValueError, AssertionError):
                assert option in ["y", "Y", ""] + [str(i) for i in range(job_list_count)], "Canceled!"
                if option in [str(i) for i in range(job_list_count)]:
                    start_index = int(option)

        results = []

        avg_result = defaultdict(list)
        if use_top_config:
            mean = lambda ll: sum(ll) / len(ll) if len(ll) > 0 else 0
            tag_num = len(set([c["tag"] for c in self.list]))

            # assert start_index == 0, "use_top_config and start_index cannot be used together"
            # assert job_list_count % tag_num == 0, "job_list_count % tag_num != 0"

        config = None
        for ci in range(start_index, job_list_count):
            if use_top_config and len(avg_result.keys()) == tag_num:
                avg_sorted_tags = sorted(avg_result.keys(), key=lambda k: mean(avg_result[k]), reverse=True)
                for group in avg_sorted_tags:
                    can_run = [c for c in self.list[start_index:] if not c.get("status") and c["tag"] == group]
                    config = can_run[0] if can_run else None
                    if config:
                        break

            elif use_top_config:
                for cci in range(start_index, job_list_count):
                    if not self.list[cci].get("status") and self.list[cci]["tag"] not in avg_result.keys():
                        config = self.list[cci]
                        break

            else:
                config = self.list[ci]

            assert config, "No config to run!"

            # 打印当前运行的配置以及结果
            if len(avg_result) > 0:
                print()
                pp_results_tuple = []
                for k in avg_result.keys():
                    fmt_result = ", ".join([f"{r:.4f}" for r in avg_result[k]])
                    pp_name = cp.green(f"▶ {k}", True) if k == config['tag'] else cp.blue(f"  {k}", True)
                    pp_result = f"\t{mean(avg_result[k]):.4f} ({len(avg_result[k])}): {fmt_result}"
                    pp_results_tuple.append((pp_name, pp_result))

                max_pp_name_len = max([len(t[0]) for t in pp_results_tuple])
                for pp_name, pp_result in pp_results_tuple:
                    print(pp_name.ljust(max_pp_name_len + 1, " "), pp_result)

                # print(f"select {config['tag']} {', '.join([f'{r:.4f}' for r in avg_result[k]])}")

            result, status = self.execute(func, ci, config, main_index=main_index, **kwargs)
            config["status"] = status

            if status != "done":
                cp.error(self.name, f"{config['tag']} {status}")
                continue

            # print(self.run_id + " Result:", end=" ")
            # cp.print_json(result)
            results.append(result)

            if use_top_config:
                avg_result[config["tag"]].append(result.get(main_index, 0))

        self.results = results
        self._generate_results_table(results)
        self.success = True

    def _generate_results_table(self, results):
        # handle results
        if len(results) == 0:
            self.results_table = None
            self.result_json = {"name": "Result is None."}
            return

        keys = list(results[0].keys())
        keys.remove("tag")
        keys.insert(0, "tag")  # tag should be the first column
        result_group = defaultdict(dict)
        for result in results:
            result_group[result["tag"]] = result_group.get(result["tag"], defaultdict(list))
            result_group[result["tag"]]["results"].append(result)

        for group in result_group.values():
            for name in keys:
                if isinstance(group["results"][0].get(name, "N/A"), (int, float)):
                    if len(group["results"]) > 1:
                        mean, h = confidence_interval([r[name] for r in group["results"]])
                        group[name] = f"{mean * 100:.1f}±{h * 100:.1f}"
                    else:
                        group[name] = f"{group['results'][0][name] * 100:.1f}"
                else:
                    group[name] = group["results"][0].get(name, "N/A")
                    if len(group["results"]) > 1:
                        group[name] += f" ({len(group['results'])})"

        cur_time = xerrors.cur_time("human")
        cp.success(self.name, "All Done! " + str(cur_time) + f" Run ID: {self.run_id}")

        # print results
        table = PrettyTable()
        result_json = {}
        table.field_names = list(keys)
        for tag, group in result_group.items():
            table.add_row([group[name] for name in keys])
            result_json[tag] = {name: group[name] for name in keys}

        table.align["tag"] = "l"
        print(table)
        self.results_table = table
        self.result_json = result_json
        with open(os.path.join(self.run_dir, "result.yaml"), "w") as f:
            yaml.dump({str(self.run_id): results}, f, sort_keys=False)
        with open(os.path.join(self.run_dir, "result_table.txt"), "w") as f:
            f.write(str(table))
        with open(os.path.join(self.run_dir, "result_parsed.yaml"), "w") as f:
            yaml.dump(result_json, f, sort_keys=False)
        # return table, result_group

    def execute(self, func, ci, config, **kwargs):
        print("\n" + "=" * 118)
        run_info = str(xerrors.cur_time("%m/%d %H:%M"))
        run_info += " " + f"{ci}/{len(self.list)} {self.run_id}"
        run_info += " " + cp.magenta(config['tag'], bold=True)
        run_info += " " + self.get_show_name(config)
        print(run_info)
        print("=" * 118)
        # print(config["tag"] + " Config:", end=" ")
        # cp.print_json(config)

        result = {}
        status = "start"

        if config["tag"] in self.skip_name_list:
            print(f"{cp.red('Skip!', bold=True)} {config['tag']} in skip_name_list: {', '.join(self.skip_name_list)}")
            status = "skip"
            return result, status

        try:
            result = func(True, **config)
            result["tag"] = config["tag"]
            status = "done"

            # 处理跳过逻辑的代码
            main_index = kwargs.get("main_index")
            skip_value = kwargs.get("skip_value")
            if main_index and skip_value:
                if result.get(main_index) and result[main_index] < skip_value:
                    self.skip_name_list.append(config["tag"])
                    print(config["tag"], f"{main_index}={result[main_index]} < {skip_value}")
                    print(f"The following config will be skipped: {', '.join(self.skip_name_list)}")

        except KeyboardInterrupt:
            cp.error(self.name, "KeyboardInterrupt: Interrupted by user!")
            status = "interrupted"
            try:
                print("10 秒后继续运行", end="")
                for i in range(10, 0, -1):
                    time.sleep(1)
                    print(f"\r{i} 秒后继续运行，使用 Ctrl+C 取消", end="")

            except KeyboardInterrupt:
                cp.error(self.name, "Shutdown by user!")
                exit(-1)

        except Exception as e:
            cp.error(self.name, traceback.format_exc())
            cp.error(self.name, f"Running Error: {e}, Continue...")
            time.sleep(20)
            status = "error"

        return result, status

    def add(self, **configs):
        """ Add a new configuration to the runner """
        combinations = self._parse_configurations(configs)
        self.runner_list.extend(combinations)

    def add_test(self, **configs):
        """ Add a new configuration to the runner """
        combinations = self._parse_configurations(configs)
        self.test_list.extend(combinations)

    @staticmethod
    def _parse_configurations(configs):
        """ Depth first search to parse all possible combinations of configurations"""
        if len(configs) == 0:
            return []

        combinations = [{}]
        for key, value in configs.items():
            if isinstance(value, list):
                new_combinations = []
                for item in value:
                    for combination in combinations:
                        new_combinations.append({**combination, key: item})
                combinations = new_combinations
            else:
                for combination in combinations:
                    combination[key] = value

        return combinations

    @staticmethod
    def _parse_index(index):
        """ Parse the configuration index """
        if isinstance(index, str):
            with open(index, "r") as f:
                index = yaml.load(f, Loader=yaml.FullLoader)
        return index

    def refine_config(self, config):
        """ Refine the configuration """
        if self.args.test_mode:
            assert config.get("test_from_ckpt"), "Please specify the checkpoint path for testing"
            if os.path.isdir(config["test_from_ckpt"]):
                config["test_from_ckpt"] = os.path.join(config["test_from_ckpt"], "config.yaml")

            with open(config["test_from_ckpt"], "r") as f:
                ckpt_config = yaml.load(f, Loader=yaml.FullLoader)
                config["tag"] = ckpt_config["tag"]
        else:
            config["tag"] = self.name

        config["tag"] += self.generate_config_tag(config)

        return config

    def modified_gpu(self):
        """ 全局 GPU 选择逻辑 """

        if not self.global_gpu:
            if self.args.gpu != "not specified":
                self.global_gpu = self.args.gpu
            else:
                self.global_gpu = xerrors.get_gpu_by_user_input()

        return self.global_gpu

    def generate_config_tag(self, config):
        """ Generate a tag for the configuration """

        def default_formatter(key, value):
            if value is True:
                return f"-{key}"
            elif value is False or value is None:
                return ""
            else:
                return f"-{key}#{value}"

        tag = ""
        for key, value in config.items():

            if key in self.block_configuration:
                continue

            formatter = self.special_content.get(key, default_formatter)
            tag += formatter(self.configuration_index.get(key, key), value)

        return tag

    def get_show_name(self, config):
        show_name = ""
        for k, v in config.items():
            if k in self.special_content and k in self.block_configuration:
                show_name += self.special_content[k](k, v)
        return show_name


def visible_length(text):
    # 使用正则表达式去除ANSI转义序列
    import re
    ansi_escape = re.compile(r"\033\[\d+;\d+m|\033\[\d+m")
    # visible_text = ansi_escape.sub('', text)
    visible_text = re.sub(ansi_escape, '', text)
    return len(visible_text)


def align_strings(input_list, split_str="|T|"):
    # 找到最长的可见字符串长度
    # max_visible_length = max(visible_length(s.replace(split_str, '')) for s in input_list)
    max_visible_length = max(len(s) for s in input_list)
    # 对每个字符串进行处理，使其长度一样，并以|T|为分隔对齐
    aligned_list = []
    for s in input_list:
        if split_str in s:
            parts = s.split(split_str)
            left_part = parts[0].ljust(max_visible_length - visible_length(parts[1]), " ")
            right_part = parts[1].rjust(visible_length(parts[1]), " ")
            aligned_string = left_part + "" + right_part
        else:
            aligned_string = s.ljust(max_visible_length + 1, " ")
        aligned_list.append(aligned_string)

    return aligned_list
