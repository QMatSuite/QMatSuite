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
package main.java;

import java.io.IOException;
import java.net.URL;

import javafx.fxml.FXMLLoader;
import main.java.job.JobManager;
import main.java.project.ProjectManager;

public class MainClass {
	public ProjectManager projectManager;
	public JobManager jobManager;
	
	
	
	public MainClass() {
		projectManager = new ProjectManager();
		jobManager = new JobManager();
	}
	public static FXMLLoader getFxmlLoader(String filename) throws IOException {
		//FXMLLoader fxmlLoader4 = new FXMLLoader(this.getClass().getResource("/main/resources/InputMd.fxml"));
		//URL url = ClassLoader.getSystemResource(filename);
		URL url = ClassLoader.getSystemClassLoader().getResource(filename);
		return new FXMLLoader(url);
	}
}
