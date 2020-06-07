/*******************************************************************************
 * Copyright (c) 2020 Haonan Huang.
 *
 *     This file is part of QuantumVITAS (Quantum Visualization Interactive 
 *     Toolkit for Ab-initio Simulations).
 *
 *     QuantumVITAS is free software: you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation, either version 3 of the License, or any 
 *     later version.
 *
 *     QuantumVITAS is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU General Public License for more details.
 *
 *     You should have received a copy of the GNU General Public License
 *     along with QuantumVITAS.  If not, see <https://www.gnu.org/licenses/gpl-3.0.txt>.
 *******************************************************************************/
package app.menus.settingTabs;

import java.io.File;
import java.net.URL;
import java.nio.file.Paths;
import java.util.ResourceBundle;

import com.programConst.Coloring;
import com.programConst.DefaultFileNames.settingKeys;

import javafx.fxml.FXML;
import javafx.fxml.Initializable;
import javafx.geometry.Insets;
import javafx.scene.control.Button;
import javafx.scene.control.TextField;
import javafx.scene.layout.AnchorPane;
import javafx.scene.layout.Background;
import javafx.scene.layout.BackgroundFill;
import javafx.scene.layout.CornerRadii;
import javafx.stage.DirectoryChooser;
import javafx.stage.Stage;
import main.MainClass;

public class PathsController implements Initializable{

	@FXML private AnchorPane acp;
	
    @FXML
    private Button openWorkspaceButton;

    @FXML
    private Button openQEPathButton;

    @FXML
    private TextField textWorkspace;

    @FXML
    private TextField textQEPath;

    private MainClass mainClass;
    
    public PathsController(MainClass mc) {
    	mainClass = mc;
	}

	@Override
	public void initialize(URL arg0, ResourceBundle arg1) {
		textQEPath.setBackground(new Background(new BackgroundFill(Coloring.defaultFile, 
				CornerRadii.EMPTY, Insets.EMPTY)));
		
		openQEPathButton.setOnAction((event) -> {

			DirectoryChooser dirChooser = new DirectoryChooser ();
			
			//go to current directory
			String currentPath = Paths.get(".").toAbsolutePath().normalize().toString();
			File tmpFile = new File(currentPath);
			if(tmpFile!=null && tmpFile.canRead()) {
				dirChooser.setInitialDirectory(tmpFile);
			}
			
			File selectedDir = dirChooser.showDialog((Stage)acp.getScene().getWindow());
			
			if(selectedDir!=null && selectedDir.canRead()) {
				mainClass.projectManager.qePath = selectedDir.getPath();
				textQEPath.setText(selectedDir.getPath());
				mainClass.projectManager.writeGlobalSettings(settingKeys.qePath.toString(),selectedDir.getPath());
				textQEPath.setBackground(new Background(new BackgroundFill(Coloring.validFile, 
						CornerRadii.EMPTY, Insets.EMPTY)));
			}
			
		});
	}
	public void loadPaths() {
		String workSpacePath = mainClass.projectManager.workSpacePath;
		String qePath = mainClass.projectManager.qePath;
		if (workSpacePath!=null) {
			textWorkspace.setText(workSpacePath);
			File wsDir = new File(workSpacePath);
			if(wsDir!=null && wsDir.canRead()) {
				textWorkspace.setBackground(new Background(new BackgroundFill(Coloring.validFile, 
						CornerRadii.EMPTY, Insets.EMPTY)));
			}
			else {
				textWorkspace.setBackground(new Background(new BackgroundFill(Coloring.invalidFile, 
						CornerRadii.EMPTY, Insets.EMPTY)));
			}
		}
		else {
			textWorkspace.setBackground(new Background(new BackgroundFill(Coloring.invalidFile, 
					CornerRadii.EMPTY, Insets.EMPTY)));
		}
		
		if(qePath!=null) {
			textQEPath.setText(qePath);
			File qeDir = new File(qePath);
			if(qeDir!=null && qeDir.canRead()) {
				textQEPath.setBackground(new Background(new BackgroundFill(Coloring.validFile, 
						CornerRadii.EMPTY, Insets.EMPTY)));
			}
			else {
				textQEPath.setBackground(new Background(new BackgroundFill(Coloring.invalidFile, 
						CornerRadii.EMPTY, Insets.EMPTY)));
			}
		}
		else {
			textQEPath.setBackground(new Background(new BackgroundFill(Coloring.invalidFile, 
					CornerRadii.EMPTY, Insets.EMPTY)));
		}
	}
}