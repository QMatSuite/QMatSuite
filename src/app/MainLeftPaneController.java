/*******************************************************************************
 * Copyright (c) 2020 Haonan Huang.
 *
 *     This file is part of QuantumVITAS (Quantum Visualization Interactive Toolkit for Ab-initio Simulations).
 *
 *     QuantumVITAS is free software: you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation, either version 3 of the License, or
 *     any later version.
 *
 *     QuantumVITAS is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU General Public License for more details.
 *
 *     You should have received a copy of the GNU General Public License
 *     along with QuantumVITAS.  If not, see <https://www.gnu.org/licenses/gpl-3.0.txt>.
 *******************************************************************************/

package app;
import java.io.File;
import java.net.URL;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.ResourceBundle;
import com.consts.Constants.EnumCalc;
import javafx.fxml.FXML;
import javafx.fxml.Initializable;
import javafx.scene.control.Button;
import javafx.scene.control.TreeItem;
import javafx.scene.control.TreeTableColumn;
import javafx.scene.control.TreeTableView;
import javafx.scene.control.cell.TreeItemPropertyValueFactory;
import javafx.scene.text.Font;
import javafx.scene.text.FontWeight;
import main.MainClass;
import project.ProjectCalcLog;

public class MainLeftPaneController implements Initializable {
	
	@FXML private TreeTableView<ProjectCalcLog> projectTree;
	@FXML public Button buttonOpenSelected,buttonCloseSelected;
	
	private TreeItem<ProjectCalcLog> projectTreeRoot;
	private MainClass mainClass;
	private HashMap<String, TreeItem<ProjectCalcLog>> projectTreeDict;
	private HashMap<String, HashMap<EnumCalc, TreeItem<ProjectCalcLog>>> projectCalcTreeDict;
	
    public MainLeftPaneController(MainClass mc) {
    	mainClass = mc;
    }

	@Override
	public void initialize(URL arg0, ResourceBundle arg1) {
		initialize();
	}
	public void initialize() {
		projectTreeDict = new HashMap<String, TreeItem<ProjectCalcLog>> ();
		projectCalcTreeDict = new HashMap<String, HashMap<EnumCalc, TreeItem<ProjectCalcLog>>>();
		
		TreeTableColumn<ProjectCalcLog, String> treeTableColumn1 = new TreeTableColumn<>("Project");
		TreeTableColumn<ProjectCalcLog, String> treeTableColumn2 = new TreeTableColumn<>("Calculation");
		TreeTableColumn<ProjectCalcLog, String> treeTableColumn3 = new TreeTableColumn<>("Steps");
		
		treeTableColumn1.setPrefWidth(90);
		treeTableColumn2.setPrefWidth(90);
		treeTableColumn3.setPrefWidth(90);
		
		treeTableColumn1.setCellValueFactory(new TreeItemPropertyValueFactory<>("project"));
		treeTableColumn2.setCellValueFactory(new TreeItemPropertyValueFactory<>("calculation"));
		treeTableColumn3.setCellValueFactory(new TreeItemPropertyValueFactory<>("steps"));

		projectTree.getColumns().add(treeTableColumn1);
		projectTree.getColumns().add(treeTableColumn2);
		projectTree.getColumns().add(treeTableColumn3);
		
		//projectTreeDict = new HashMap<String, TreeItem<String>>();
		//projectCalcTreeDict = new HashMap<String, HashMap<EnumCalc, TreeItem<String>>>();
//		projectTreeDict = new HashMap<String, TreeItem<ProjectCalcLog>>();
//		projectCalcTreeDict = new HashMap<String, HashMap<EnumCalc, TreeItem<ProjectCalcLog>>>();
				
		//add listener
		
//		projectTree.getSelectionModel().selectedItemProperty().addListener((v, oldValue, newValue) -> { 
//			if (newValue!=null || projectTreeDict == null) {
//				/*for (String key : projectTreeDict.keySet()) {
//				if (projectTreeDict.get(key)==newValue) {
//					//must be project branch. A bit complicated here
//					
//					if (currentProject==key) return;//if project still the same!
//					//handle old part of the tree
//					if (currentProject!=null && projectTreeDict.containsKey(currentProject)) {
//						projectTreeDict.get(currentProject).setExpanded(false);
//					}
//					//handle new project
//					//workSpaceTabPane.getSelectionModel().select
//					mainClass.projectManager.setActiveProject(key);
//					currentProject=key;
//					projectTreeDict.get(currentProject).setExpanded(true);
//					if (currentCalcDict.get(currentProject)!=null) {
//						openCalc(currentCalcDict.get(currentProject));
//					}
//					//projectCalcTreeDict.get(currentProject).get(key)
//					//updateCalcTree();
//					loadProjectParameters();	
//					
//					return;//just need first match
//				}}*/
//				if (currentProject==null || !projectCalcTreeDict.containsKey(currentProject)) return;
//				for (EnumCalc key2 : projectCalcTreeDict.get(currentProject).keySet()) {
//					if (projectCalcTreeDict.get(currentProject).get(key2)==newValue) {
//						//must be in a calculation branch, just open the calculation
//						openCalc(key2); return;//just need first match
//					}
//				}
//			}
//		});
		
		projectTree.getSelectionModel().selectedItemProperty().addListener((v, oldValue, newValue) -> { 
			if(newValue==null || projectTreeRoot==null) return;
			else {
				while(newValue!=null && !projectTreeRoot.getChildren().contains(newValue)) {
					newValue=newValue.getParent();//go back up until the children of the root
				}
				if(newValue==null) return;
				String pj = newValue.getValue().getProject();
				setOpenCloseButtons(!mainClass.projectManager.containsProject(pj));
			}
		});
		
		projectTreeRoot = new TreeItem<ProjectCalcLog>(new ProjectCalcLog("Projects","",""));
		projectTree.setRoot(projectTreeRoot);
		projectTreeRoot.setExpanded(true);
	}
	public void setOpenCloseButtons(boolean bl) {
		//true -> can open
		//false -> can close
		if(bl) {
			buttonCloseSelected.setFont(Font.font(buttonCloseSelected.getFont().toString(), FontWeight.NORMAL, buttonCloseSelected.getFont().getSize()));
			buttonOpenSelected.setFont(Font.font(buttonOpenSelected.getFont().toString(), FontWeight.BOLD, buttonOpenSelected.getFont().getSize()));
		}
		else {
			buttonCloseSelected.setFont(Font.font(buttonCloseSelected.getFont().toString(), FontWeight.BOLD, buttonCloseSelected.getFont().getSize()));
			buttonOpenSelected.setFont(Font.font(buttonOpenSelected.getFont().toString(), FontWeight.NORMAL, buttonOpenSelected.getFont().getSize()));
		}
	}
	public String getSelectedProject() {
		TreeItem<ProjectCalcLog> ti = projectTree.getSelectionModel().getSelectedItem();
		if(ti==null || projectTreeRoot==null) return null;
		else {
			//checking ti!=null will increase program rigidity, but not necessary
			while(ti!=null && !projectTreeRoot.getChildren().contains(ti)) {
				ti=ti.getParent();//go back up until the children of the root
			}
			if(ti==null) return null;
			return ti.getValue().getProject();
		}
		
	}
	public void closeProject(String pj) {
		if(projectCalcTreeDict.get(pj)!=null) {
			for (TreeItem<ProjectCalcLog> value : projectCalcTreeDict.get(pj).values()) {
				value.getParent().getChildren().remove(value);
			}
		}
		projectCalcTreeDict.get(pj).clear();
	}
//	public void removeProject(String pj) {
//		
//	    projectTreeRoot.getChildren().remove(projectTreeDict.get(pj));
//	    projectTreeDict.remove(pj);
//		
//		projectCalcTreeDict.remove(pj);
//	}
	public void addProject(String pj) {
		TreeItem<ProjectCalcLog> ti = new TreeItem<ProjectCalcLog>(new ProjectCalcLog(pj,"",""));
		projectTreeRoot.getChildren().add(ti);
		projectTreeRoot.setExpanded(true);
		projectTreeDict.put(pj,ti);
		projectCalcTreeDict.put(pj, new HashMap<EnumCalc, TreeItem<ProjectCalcLog>>());
	}
	public void updateCalcTree(EnumCalc ec) {
		String currentProject = mainClass.projectManager.getActiveProjectName();
		if (currentProject!=null && projectTreeDict.containsKey(currentProject) && projectCalcTreeDict.containsKey(currentProject)) {
			if (ec==null) {
				return;
			}
			if (!projectCalcTreeDict.get(currentProject).containsKey(ec)) {
				//add tree item if not already exists
				TreeItem<ProjectCalcLog> ti = new TreeItem<ProjectCalcLog>(new ProjectCalcLog("",ec.getShort(),""));
				projectCalcTreeDict.get(currentProject).put(ec, ti);
				projectTreeDict.get(currentProject).getChildren().add(ti);
				//expand project tree, select active calc item
				projectTreeDict.get(currentProject).setExpanded(true);
				//int row = projectTree.getRow(ti);
				//projectTree.getSelectionModel().select(row);
			}
			else {
				//expand project tree, select active calc item
				projectTreeDict.get(currentProject).setExpanded(true);
//				//int row = projectTree.getRow(projectCalcTreeDict.get(currentProject).get(ec));
//				//projectTree.getSelectionModel().select(row);
			}
			
		}
	}
	public void updateFullCalcTree() {
		for(EnumCalc ec : mainClass.projectManager.getCurrentCalcList()) {
			updateCalcTree(ec);
		}
	}
	public void updateCalcTree() {
		if (mainClass.projectManager.existCurrentCalc()) {
			updateCalcTree(mainClass.projectManager.getCurrentCalcName());
		}
	}
	public void clearTree() {
		projectTreeRoot.getChildren().clear();
		projectTreeDict.clear();
		projectCalcTreeDict.clear();
	}
	public void updateProjects(File wsDir) {
		if (wsDir==null || !wsDir.canRead()) return;
//		try (Stream<Path> walk = Files.walk(wsDir.toPath())) {
//
////			List<String> result = walk.filter(Files::isDirectory)
////					.map(x -> x.toString()).collect(Collectors.toList());
//			List<Path> result = walk.filter(Files::isDirectory).collect(Collectors.toList());
//			
//			for (Path temp : result) {
//				String tmp = temp.getFileName().toString();
//				TreeItem<ProjectCalcLog> ti = new TreeItem<ProjectCalcLog>(new ProjectCalcLog(tmp,"",""));
//				projectTreeRoot.getChildren().add(ti);
//				projectTreeRoot.setExpanded(true);
//				projectTreeDict.put(tmp,ti);
//				projectCalcTreeDict.put(tmp, new HashMap<EnumCalc, TreeItem<ProjectCalcLog>>());
//			}
//			
//			//result.forEach(System.out::println);
//
//		} catch (IOException e) {
//			e.printStackTrace();
//		}
		
		File[] directories = wsDir.listFiles(File::isDirectory);
		ArrayList<String> nameTmp = new ArrayList<String>();
		for (File temp : directories) {
			String tmp = temp.getName();
			if(!projectTreeDict.containsKey(tmp)) {
				TreeItem<ProjectCalcLog> ti = new TreeItem<ProjectCalcLog>(new ProjectCalcLog(tmp,"",""));
				projectTreeRoot.getChildren().add(ti);
				projectTreeRoot.setExpanded(true);
				projectTreeDict.put(tmp,ti);
				projectCalcTreeDict.put(tmp, new HashMap<EnumCalc, TreeItem<ProjectCalcLog>>());
			}	
		}
		
	}
}
