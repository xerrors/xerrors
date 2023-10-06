
import os
import time
import random
import argparse
from collections import defaultdict
from prettytable import PrettyTable

import yaml
import traceback
import xerrors
import xerrors.cprint as cp
from xerrors.metrics import confidence_interval

## TODO
# Resume from checkpoint

class Runner(object):
    def __init__(self,
                 name="Runner",
                 run_id=None,
                 log_dir="output",
                 configuation_index=None,
                 block_configuation=None,):

        self.name = name
        self.configuation_index = self._parse_index(configuation_index)
        self.block_configuation = block_configuation

        self.global_gpu = None

        self.args = runner_parser()
        self.list = []
        self.runner_list = []
        self.test_list = []

        # result
        self.result = {}

        self.run_id = run_id or f"RUN_{xerrors.cur_time()}"
        self.run_dir = os.path.join(log_dir, f"{self.name}-{self.run_id}")
        os.makedirs(self.run_dir, exist_ok=True)

        # Temp
        self.special_content = {
            "seed": lambda k,v: f"-SEED@{v}",
            "dataset_config": lambda k,v: f"-D{v.split('/')[-1].split('.')[0][-1:]}",
            "gpu": lambda k,v: f"-GPU#{v}",
        }

        # skip
        self.skip_name_list = []

    def run(self, func, sort_by_seed=False, gpu_id: str="", **kwargs):

        gpu_id = gpu_id or self.modified_gpu()

        if self.args.test_mode:
            self.list = self.test_list
        else:
            self.list = self.runner_list

        if len(self.list) == 0:
            cp.warning(self.name, "No configurations found")
            return

        if sort_by_seed:
            self.list = sorted(self.list, key=lambda x: x["seed"] if x.get("seed") else 0)

        print(cp.green(f"\nRunning {self.name} with {len(self.list)} configurations", bold=True))
        for config in self.list:
            config = self.refine_config(config)
            config["run_id"] = self.run_id
            config["gpu"] = gpu_id # 不使用 config 中指定的 gpu

            show_name = ""
            for k, v in config.items():
                if k in self.special_content and k in self.block_configuation:
                    show_name += self.special_content[k](k, v)
            # print(f" - {config['tag']}" + (f" (@{config['seed']})" if "seed" in config else ""))
            print(f" - {config['tag']} ({show_name})")

        # 确认，开始运行，输入y确认，其余取消
        if not self.args.debug and not self.args.Y:
            option = input("Confirm to run? (y/n): ")
            if option != "y" and option != "Y":
                cp.error(self.name, "Canceled!")
                exit()

        results = []
        for ci, config in enumerate(self.list):
            # 定义了 start_index，用于继续运行之前断开的任务
            if kwargs.get("start_index") and ci < kwargs["start_index"]:
                continue

            result, status = self.execute(func, ci, config, **kwargs)

            if status != "done":
                continue

            print(result["tag"] + " Result:", end=" ")
            cp.print_json(result)
            results.append(result)

        self.results = results
        self._generate_results_table(results)

    def _generate_results_table(self, results):
        # handle results
        keys = list(results[0].keys())
        keys.remove("tag")
        keys.insert(0, "tag") # tag should be the first column
        result_group = defaultdict(dict)
        for result in results:
            result_group[result["tag"]] = result_group.get(result["tag"], defaultdict(list))
            result_group[result["tag"]]["results"].append(result)

        for group in result_group.values():
            for name in keys:
                if isinstance(group["results"][0].get(name, "N/A"), (int, float)):
                    mean, h = confidence_interval([r[name] for r in group["results"]])
                    group[name] = f"{mean*100:.1f}±{h:.1f}"
                else:
                    group[name] = group["results"][0].get(name, "N/A")
                    if len(group["results"]) > 1:
                        group[name] += f" ({len(group['results'])})"

        cur_time = xerrors.cur_time("human")
        cp.success(self.name, "All Done! " + cur_time)

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
        # return table, result_group

    def execute(self, func, ci, config, **kwargs):
        print("\n" + "=" * 80)
        print(f"{xerrors.cur_time('human')} Runing: {ci}/{len(self.list)} {cp.magenta(config['tag'], bold=True)}")
        print("=" * 80)
        print(config["tag"] + " Config:", end=" ")
        cp.print_json(config)

        result = {}
        status = "start"

        if config["tag"] in self.skip_name_list:
            print(config["tag"], f"Skip! {config['tag']} in skip_name_list")
            status = "skip"
            return result, status

        try:
            result = func(True, **config)
            result["tag"] = config["tag"]
            print(config["tag"], "Done!")
            status = "done"

            # 处理跳过逻辑的代码
            skip_index = kwargs.get("skip_index")
            skip_value = kwargs.get("skip_value")
            if skip_index and skip_value:
                if result.get(skip_index) and result[skip_index] < skip_value:
                    self.skip_name_list.append(config["tag"])
                    print(config["tag"], f"{cp.red('Skip!')} {skip_index}={result[skip_index]} < {skip_value}")
                    status = "skip"


        except KeyboardInterrupt:
            cp.error(self.name, "KeyboardInterrupt: Interrupted by user!")
            status = "interrupted"
            try:
                # time.sleep(3)
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
            status = "error"

        return result, status


    def add(self, **configs):
        """ Add a new configuration to the runner """
        combinations = self._parse_configuations(configs)
        self.runner_list.extend(combinations)

    def add_test(self, **configs):
        """ Add a new configuration to the runner """
        combinations = self._parse_configuations(configs)
        self.test_list.extend(combinations)

    def _parse_configuations(self, configs):
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

    def _parse_index(self, index):
        """ Parse the configuation index """
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

            if key in self.block_configuation:
                continue

            formatter = self.special_content.get(key, default_formatter)
            tag += formatter(self.configuation_index.get(key, key), value)

        return tag

def runner_parser():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-Y", action="store_true", help="Confirm to run")
    parser.add_argument("-T", "--test-mode", action="store_true", help="Run Test")
    parser.add_argument("--gpu", type=str, default="not specified")
    parser.add_argument("--output", type=str, default="output", help="Output directory")
    parser.add_argument("--debug", action="store_true", help="Debug mode")
    args, _ = parser.parse_known_args()
    return args
